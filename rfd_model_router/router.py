import sqlite3
import time
import warnings
from collections.abc import Generator
from pathlib import Path

import yaml

from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.base import BaseAdapter
from .adapters.gemini_adapter import GeminiAdapter
from .adapters.groq_adapter import GroqAdapter
from .adapters.openrouter_adapter import OpenRouterAdapter
from .logger import DB_PATH, log_request
from .pricer import calculate_cost, estimate_tokens
from .throttle import _throttle

CONFIG_PATH = Path(__file__).parent.parent / "routing_config.yaml"

RETRY_STATUS_CODES = {429, 503, 502, 504}
MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0  # seconds
CALL_TIMEOUT_SECONDS = 30

_ADAPTERS: dict[str, type[BaseAdapter]] = {
    "anthropic": AnthropicAdapter,
    "groq": GroqAdapter,
    "gemini": GeminiAdapter,
    "openrouter": OpenRouterAdapter,
}


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError("routing_config.yaml must contain a YAML mapping")
    return config


def get_adapter(provider: str) -> BaseAdapter:
    cls = _ADAPTERS.get(provider)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    return cls()


class ThrottleError(Exception):
    pass


class BudgetExceededError(Exception):
    pass


def _is_retriable(e):
    status = getattr(e, "status_code", None) or getattr(e, "status", None)
    if status == 402:  # Insufficient credits — never retry
        return False
    if status in RETRY_STATUS_CODES:
        return True
    if isinstance(e, TimeoutError):
        return True
    return False


def _get_daily_spend(provider: str) -> float:
    """Sum cost_usd from requests table for provider today. Returns 0.0 on error."""
    try:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0.0)
                FROM requests
                WHERE provider = ? AND timestamp LIKE ?
                """,
                (provider, f"{today}%"),
            )
            result = cursor.fetchone()
            return result[0] if result else 0.0
    except Exception:
        return 0.0


def _check_estimation(messages: list[dict], system_prompt: str | None, entry: dict) -> None:
    """Pre-call token estimation check. Raises ValueError if exceeds 90% of context limit."""
    estimated = estimate_tokens(messages, system_prompt)
    max_ctx = entry.get("max_context_tokens")
    if max_ctx and estimated > int(max_ctx * 0.9):
        raise ValueError(
            f"Estimated {estimated} tokens exceeds 90% of {entry['model']} "
            f"context limit ({max_ctx}). Reduce input size."
        )


def _check_throttle(
    provider: str,
    model: str,
    fallback_provider: str | None,
    fallback_model: str | None,
    rate_limits: dict,
) -> tuple[str, str]:
    """Throttle check with fallback. Returns (provider, model) after check. Raises ThrottleError if throttled and no fallback."""
    rpm = rate_limits.get(provider, {}).get("requests_per_minute", 0)
    if not _throttle.is_allowed(provider, rpm):
        if fallback_provider and fallback_model:
            fallback_rpm = rate_limits.get(fallback_provider, {}).get("requests_per_minute", 0)
            if _throttle.is_allowed(fallback_provider, fallback_rpm):
                return fallback_provider, fallback_model
        raise ThrottleError(f"Provider '{provider}' rate limit exceeded ({rpm} RPM)")
    return provider, model


def _check_budget(
    provider: str,
    model: str,
    fallback_provider: str | None,
    fallback_model: str | None,
    budgets: dict,
) -> tuple[str, str]:
    """Budget check with fallback. Returns (provider, model) after check. Raises BudgetExceededError if exceeded and no fallback."""
    daily_limit = budgets.get(provider, {}).get("daily_limit_usd", 0.0)
    if daily_limit > 0.0:
        today_spend = _get_daily_spend(provider)
        if today_spend >= daily_limit:
            if fallback_provider and fallback_model:
                fallback_limit = budgets.get(fallback_provider, {}).get("daily_limit_usd", 0.0)
                fallback_spend = _get_daily_spend(fallback_provider)
                if fallback_limit == 0.0 or fallback_spend < fallback_limit:
                    return fallback_provider, fallback_model
                else:
                    raise BudgetExceededError(
                        f"Provider '{provider}' daily budget ${daily_limit:.2f} exceeded "
                        f"(spent ${today_spend:.4f} today)"
                    )
            else:
                raise BudgetExceededError(
                    f"Provider '{provider}' daily budget ${daily_limit:.2f} exceeded "
                    f"(spent ${today_spend:.4f} today)"
                )
    return provider, model


def _complete_with_retry(adapter, model, messages, system_prompt):
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return adapter.complete(
                model=model,
                messages=messages,
                system_prompt=system_prompt,
                timeout=CALL_TIMEOUT_SECONDS,
            )
        except Exception as e:
            if _is_retriable(e) and attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                last_error = e
                continue
            raise
    raise last_error


def route(
    task_type: str,
    messages: list[dict],
    system_prompt: str | None = None,
) -> tuple[str, str, str, int, int]:
    config = load_config()
    entry = config.get(task_type)
    if entry is None:
        warnings.warn(f"Unknown task_type '{task_type}', falling back to default")
        entry = config.get("default")
    provider = entry["provider"]
    model = entry["model"]
    fallback_provider = entry.get("fallback_provider")
    fallback_model = entry.get("fallback_model")
    rate_limits = config.get("rate_limits", {})
    budgets = config.get("budgets", {})

    # 1. Pre-call token estimation
    _check_estimation(messages, system_prompt, entry)

    # 2. Throttle check
    provider, model = _check_throttle(
        provider, model, fallback_provider, fallback_model, rate_limits
    )

    # 3. Budget check
    provider, model = _check_budget(
        provider, model, fallback_provider, fallback_model, budgets
    )

    adapter = get_adapter(provider)
    try:
        text, input_tokens, output_tokens = _complete_with_retry(
            adapter, model, messages, system_prompt
        )
        # 4. Cost calculation after call
        cost = calculate_cost(input_tokens, output_tokens, entry.get("pricing"))
        log_request(
            task_type,
            provider,
            model,
            input_tokens,
            output_tokens,
            0,  # duration_ms not tracked here
            True,
            cost_usd=cost,
        )
        return text, provider, model, input_tokens, output_tokens
    except Exception as primary_error:
        if fallback_provider and fallback_model:
            fallback_adapter = get_adapter(fallback_provider)
            text, input_tokens, output_tokens = _complete_with_retry(
                fallback_adapter, fallback_model, messages, system_prompt
            )
            cost = calculate_cost(input_tokens, output_tokens, entry.get("pricing"))
            log_request(
                task_type,
                fallback_provider,
                fallback_model,
                input_tokens,
                output_tokens,
                0,
                True,
                cost_usd=cost,
            )
            return text, fallback_provider, fallback_model, input_tokens, output_tokens
        raise primary_error


def route_stream(
    task_type: str,
    messages: list[dict],
    system_prompt: str | None = None,
) -> Generator[str, None, dict]:
    """
    Yields text chunks. Returns metadata dict on exhaustion:
    {"provider": str, "model": str, "input_tokens": int,
     "output_tokens": int, "cost_usd": float}

    No retry. Throttle and budget checks apply before stream starts.
    Pre-call token estimation applies.
    """
    config = load_config()
    entry = config.get(task_type) or config["default"]
    provider = entry["provider"]
    model = entry["model"]
    fallback_provider = entry.get("fallback_provider")
    fallback_model = entry.get("fallback_model")
    rate_limits = config.get("rate_limits", {})
    budgets = config.get("budgets", {})

    # Reuse existing checks — estimate, throttle, budget
    _check_estimation(messages, system_prompt, entry)
    provider, model = _check_throttle(
        provider, model, fallback_provider, fallback_model, rate_limits
    )
    provider, model = _check_budget(
        provider, model, fallback_provider, fallback_model, budgets
    )

    adapter = get_adapter(provider)
    gen = adapter.stream(model, messages, system_prompt)

    input_tokens = output_tokens = 0
    try:
        while True:
            chunk = next(gen)
            yield chunk
    except StopIteration as e:
        if e.value:
            input_tokens, output_tokens = e.value

    cost = calculate_cost(input_tokens, output_tokens, entry.get("pricing"))
    log_request(
        task_type,
        provider,
        model,
        input_tokens,
        output_tokens,
        0,
        True,
        cost_usd=cost,
    )

    return {
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
    }

import time
import warnings
from pathlib import Path

import yaml

from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.base import BaseAdapter
from .adapters.gemini_adapter import GeminiAdapter
from .adapters.groq_adapter import GroqAdapter
from .adapters.openrouter_adapter import OpenRouterAdapter

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


def _is_retriable(e):
    status = getattr(e, "status_code", None) or getattr(e, "status", None)
    if status in RETRY_STATUS_CODES:
        return True
    if isinstance(e, TimeoutError):
        return True
    return False


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
    adapter = get_adapter(provider)
    try:
        text, input_tokens, output_tokens = _complete_with_retry(
            adapter, model, messages, system_prompt
        )
        return text, provider, model, input_tokens, output_tokens
    except Exception as primary_error:
        fallback_provider = entry.get("fallback_provider")
        fallback_model = entry.get("fallback_model")
        if fallback_provider and fallback_model:
            fallback_adapter = get_adapter(fallback_provider)
            text, input_tokens, output_tokens = _complete_with_retry(
                fallback_adapter, fallback_model, messages, system_prompt
            )
            return text, fallback_provider, fallback_model, input_tokens, output_tokens
        raise primary_error

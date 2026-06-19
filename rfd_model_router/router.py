import warnings
from pathlib import Path

import yaml

from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.base import BaseAdapter
from .adapters.gemini_adapter import GeminiAdapter
from .adapters.groq_adapter import GroqAdapter
from .adapters.openrouter_adapter import OpenRouterAdapter

CONFIG_PATH = Path(__file__).parent.parent / "routing_config.yaml"

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
    text, input_tokens, output_tokens = adapter.complete(
        model=model, messages=messages, system_prompt=system_prompt
    )
    return text, provider, model, input_tokens, output_tokens

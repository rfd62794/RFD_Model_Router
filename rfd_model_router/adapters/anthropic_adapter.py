import os

from anthropic import Anthropic

from .base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    def __init__(self):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> tuple[str, int, int]:
        kwargs = {"model": model, "messages": messages, "max_tokens": 1024}
        if system_prompt is not None:
            kwargs["system"] = system_prompt
        response = self.client.messages.create(**kwargs)
        text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        return text, input_tokens, output_tokens

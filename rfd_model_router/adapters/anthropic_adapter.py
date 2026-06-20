import os

from anthropic import Anthropic
from collections.abc import Generator

from .base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    def __init__(self, timeout: int = 30):
        self.client = Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=timeout,
        )

    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> tuple[str, int, int]:
        kwargs = {"model": model, "messages": messages, "max_tokens": 1024}
        if system_prompt is not None:
            kwargs["system"] = system_prompt
        response = self.client.messages.create(**kwargs)
        text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        return text, input_tokens, output_tokens

    def stream(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> Generator[str, None, tuple[int, int]]:
        input_tokens = output_tokens = 0
        with self.client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system_prompt or "",
            messages=messages,
        ) as s:
            for text in s.text_stream:
                yield text
            usage = s.get_final_message().usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
        return (input_tokens, output_tokens)

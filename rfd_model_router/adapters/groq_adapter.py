import os

from collections.abc import Generator
from groq import Groq

from .base import BaseAdapter


class GroqAdapter(BaseAdapter):
    def __init__(self, timeout: int = 30):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"), timeout=timeout)

    def _build_messages(self, messages: list[dict], system_prompt: str | None) -> list[dict]:
        msgs = list(messages)
        if system_prompt is not None:
            msgs = [{"role": "system", "content": system_prompt}] + msgs
        return msgs

    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> tuple[str, int, int]:
        msgs = self._build_messages(messages, system_prompt)
        response = self.client.chat.completions.create(model=model, messages=msgs)
        text = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        return text, input_tokens, output_tokens

    def stream(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> Generator[str, None, tuple[int, int]]:
        msgs = self._build_messages(messages, system_prompt)
        input_tokens = output_tokens = 0
        response = self.client.chat.completions.create(
            model=model, messages=msgs, stream=True, stream_options={"include_usage": True}
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens
        return (input_tokens, output_tokens)

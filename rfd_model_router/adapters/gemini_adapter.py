import os

import google.genai as genai
from collections.abc import Generator
from google.genai import types

from .base import BaseAdapter


class GeminiAdapter(BaseAdapter):
    def __init__(self, timeout: int = 30):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.timeout = timeout

    def _build_contents(self, messages: list[dict], system_prompt: str | None) -> list:
        contents = []
        if system_prompt:
            contents.append(
                types.Content(role="user", parts=[types.Part(text=system_prompt)])
            )
        for msg in messages:
            contents.append(
                types.Content(role=msg["role"], parts=[types.Part(text=msg["content"])])
            )
        return contents

    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> tuple[str, int, int]:
        contents = self._build_contents(messages, system_prompt)
        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=timeout)
            ),
        )
        text = response.text
        usage = response.usage_metadata
        return text, usage.prompt_token_count or 0, usage.candidates_token_count or 0

    def stream(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> Generator[str, None, tuple[int, int]]:
        contents = self._build_contents(messages, system_prompt)
        input_tokens = output_tokens = 0
        for chunk in self.client.models.generate_content_stream(
            model=model, contents=contents
        ):
            if chunk.text:
                yield chunk.text
            if chunk.usage_metadata:
                input_tokens = chunk.usage_metadata.prompt_token_count or 0
                output_tokens = chunk.usage_metadata.candidates_token_count or 0
        return (input_tokens, output_tokens)

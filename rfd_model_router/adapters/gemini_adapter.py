import os

import google.genai as genai
from google.genai import types

from .base import BaseAdapter


class GeminiAdapter(BaseAdapter):
    def __init__(self, timeout: int = 30):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.timeout = timeout

    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> tuple[str, int, int]:
        contents = []
        if system_prompt:
            contents.append(
                types.Content(role="user", parts=[types.Part(text=system_prompt)])
            )
        for msg in messages:
            contents.append(
                types.Content(role=msg["role"], parts=[types.Part(text=msg["content"])])
            )

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

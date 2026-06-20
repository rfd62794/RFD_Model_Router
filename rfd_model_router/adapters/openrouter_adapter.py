import os
from collections.abc import Generator
from openai import OpenAI
from .base import BaseAdapter

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
ATTRIBUTION_HEADERS = {
    "HTTP-Referer": "https://rfditservices.com",
    "X-Title": "RFD Model Router",
}

class OpenRouterAdapter(BaseAdapter):
    def __init__(self, timeout: int = 30):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            timeout=timeout,
            default_headers=ATTRIBUTION_HEADERS,
        )

    def _build_messages(self, messages, system_prompt):
        msgs = list(messages)
        if system_prompt is not None:
            msgs = [{"role": "system", "content": system_prompt}] + msgs
        return msgs

    def complete(self, model, messages, system_prompt=None, timeout=30):
        msgs = self._build_messages(messages, system_prompt)
        response = self.client.chat.completions.create(
            model=model,
            messages=msgs,
        )
        text = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        return text, input_tokens, output_tokens

    def stream(self, model, messages, system_prompt=None, timeout=30) -> Generator[str, None, tuple[int, int]]:
        msgs = self._build_messages(messages, system_prompt)
        input_tokens = output_tokens = 0
        response = self.client.chat.completions.create(
            model=model,
            messages=msgs,
            stream=True,
            stream_options={"include_usage": True},  # Required for token counts
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.choices and getattr(chunk.choices[0], "finish_reason", None) == "error":
                break  # Mid-stream error — stop cleanly
            if hasattr(chunk, "usage") and chunk.usage:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0
        return (input_tokens, output_tokens)

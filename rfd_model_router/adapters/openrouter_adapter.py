import os

from openai import OpenAI

from .base import BaseAdapter


class OpenRouterAdapter(BaseAdapter):
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )

    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> tuple[str, int, int]:
        msgs = list(messages)
        if system_prompt is not None:
            msgs = [{"role": "system", "content": system_prompt}] + msgs
        response = self.client.chat.completions.create(model=model, messages=msgs)
        text = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        return text, input_tokens, output_tokens

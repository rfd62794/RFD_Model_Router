import os

import google.generativeai as genai

from .base import BaseAdapter


class GeminiAdapter(BaseAdapter):
    def __init__(self):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> tuple[str, int, int]:
        gemini_messages = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_messages.append({"role": role, "parts": [msg["content"]]})

        model_instance = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )
        response = model_instance.generate_content(gemini_messages)
        text = response.text
        return text, 0, 0

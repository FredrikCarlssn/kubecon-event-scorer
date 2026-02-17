"""OpenAI GPT AI provider."""

from __future__ import annotations

import os

from providers.base import AIProvider


class OpenAIProvider(AIProvider):

    @property
    def default_model(self) -> str:
        return "gpt-5.2"

    @property
    def name(self) -> str:
        return "openai"

    def _call_api(self, system: str, user: str) -> str:
        from openai import OpenAI

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Export it or pass --api-key."
            )

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content

"""Google Gemini AI provider."""

from __future__ import annotations

import os

from providers.base import AIProvider


class GeminiProvider(AIProvider):

    @property
    def default_model(self) -> str:
        return "gemini-3-pro-preview"

    @property
    def name(self) -> str:
        return "gemini"

    def _call_api(self, system: str, user: str) -> str:
        from google import genai

        api_key = self.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Export it or pass --api-key."
            )

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=user,
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.3,
            ),
        )
        return response.text

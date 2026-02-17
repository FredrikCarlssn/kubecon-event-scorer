"""Anthropic Claude AI provider."""

from __future__ import annotations

import os

from providers.base import AIProvider


class AnthropicProvider(AIProvider):

    @property
    def default_model(self) -> str:
        return "claude-opus-4-6"

    @property
    def name(self) -> str:
        return "claude"

    def _call_api(self, system: str, user: str) -> str:
        import anthropic

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Export it or pass --api-key."
            )

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

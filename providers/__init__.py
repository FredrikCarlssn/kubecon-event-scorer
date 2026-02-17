"""AI provider factory."""

from __future__ import annotations

from providers.base import AIProvider


def get_provider(
    name: str,
    model: str | None = None,
    api_key: str | None = None,
) -> AIProvider:
    """Create an AI provider by name."""
    if name == "claude":
        from providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=model, api_key=api_key)
    elif name == "openai":
        from providers.openai_provider import OpenAIProvider
        return OpenAIProvider(model=model, api_key=api_key)
    elif name == "gemini":
        from providers.gemini_provider import GeminiProvider
        return GeminiProvider(model=model, api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {name}. Use: claude, openai, gemini")

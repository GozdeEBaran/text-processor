from app.providers.base import AISchemaError, AIServiceError, BaseProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.openai_provider import OpenAIProvider

_cache: dict[str, BaseProvider] = {}


def get_provider(name: str) -> BaseProvider:
    if name not in _cache:
        if name == "anthropic":
            _cache[name] = AnthropicProvider()
        elif name == "openai":
            _cache[name] = OpenAIProvider()
        else:
            raise ValueError(f"Unknown provider: '{name}'. Choose from: anthropic, openai")
    return _cache[name]


__all__ = ["get_provider", "BaseProvider", "AIServiceError", "AISchemaError"]

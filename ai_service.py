from provider import AnthropicProvider, AIServiceError, AISchemaError

_default_provider = AnthropicProvider()


def analyze_text(text: str) -> dict:
    return _default_provider.analyze(text)


__all__ = ["analyze_text", "AIServiceError", "AISchemaError"]

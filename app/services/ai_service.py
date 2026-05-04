from app.config import PRIMARY_PROVIDER
from app.providers import get_provider


def analyze_text(text: str, provider_name: str = PRIMARY_PROVIDER) -> dict:
    return get_provider(provider_name).analyze(text)

import os
from dotenv import load_dotenv

load_dotenv()

PRIMARY_PROVIDER = os.getenv("PROVIDER", "anthropic")

ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
OPENAI_MODEL = "gpt-4o"

MAX_RETRIES = 2
TIMEOUT_SECONDS = 30

_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_MODEL_MAP = {
    "anthropic": ANTHROPIC_MODEL,
    "openai": OPENAI_MODEL,
}

SUPPORTED_PROVIDERS = list(_ENV_VARS.keys())

SERVICE_API_KEY = os.getenv("API_KEY")


def get_api_key(provider: str = PRIMARY_PROVIDER) -> str:
    env_var = _ENV_VARS.get(provider)
    if not env_var:
        raise EnvironmentError(f"Unknown provider: '{provider}'. Choose from: {SUPPORTED_PROVIDERS}")
    key = os.getenv(env_var)
    if not key:
        raise EnvironmentError(f"{env_var} is not set. Add it to your .env file.")
    return key


def get_model_name(provider: str = PRIMARY_PROVIDER) -> str:
    return _MODEL_MAP.get(provider, ANTHROPIC_MODEL)

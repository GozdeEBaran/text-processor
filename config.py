import os
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "claude-sonnet-4-20250514"
PRIMARY_PROVIDER = "anthropic"
MAX_RETRIES = 2
TIMEOUT_SECONDS = 30

_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
}


def get_api_key(provider: str = PRIMARY_PROVIDER) -> str:
    env_var = _ENV_VARS.get(provider, "ANTHROPIC_API_KEY")
    key = os.getenv(env_var)
    if not key:
        raise EnvironmentError(f"{env_var} is not set. Add it to your .env file.")
    return key

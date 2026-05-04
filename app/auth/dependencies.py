from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import SERVICE_API_KEY

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Security(_api_key_header)) -> None:
    """Validates the X-API-Key header when SERVICE_API_KEY is configured.
    If API_KEY is not set in the environment, auth is disabled (dev mode)."""
    if not SERVICE_API_KEY:
        return
    if key != SERVICE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

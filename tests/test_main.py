import logging
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import AISchemaError, AIServiceError

client = TestClient(app)

VALID_TEXT = "This is a sufficiently long test text to pass the minimum length validation."
MOCK_VALID_RESULT = {
    "summary": "The text is a test.",
    "action_items": ["Do X", "Review Y", "Follow up on Z"],
}


def make_tool_use_response(data: dict) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = data
    mock = MagicMock()
    mock.content = [tool_block]
    mock.id = "msg_test123"
    return mock


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_analyze_happy_path():
    with patch("app.services.ai_service.get_provider") as mock_factory:
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = MOCK_VALID_RESULT
        mock_factory.return_value = mock_provider
        response = client.post("/analyze", json={"text": VALID_TEXT})

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "The text is a test."
    assert data["action_items"] == ["Do X", "Review Y", "Follow up on Z"]
    assert data["input_length"] == len(VALID_TEXT)
    assert "model" in data
    assert "provider" in data


def test_analyze_with_explicit_provider():
    with patch("app.services.ai_service.get_provider") as mock_factory:
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = MOCK_VALID_RESULT
        mock_factory.return_value = mock_provider
        response = client.post("/analyze", json={"text": VALID_TEXT, "provider": "anthropic"})

    assert response.status_code == 200
    assert response.json()["provider"] == "anthropic"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_rejects_text_below_minimum_length():
    response = client.post("/analyze", json={"text": "short"})
    assert response.status_code == 400
    assert "20 characters" in response.json()["detail"][0]


def test_rejects_missing_text_field():
    response = client.post("/analyze", json={})
    assert response.status_code == 400


def test_rejects_oversized_input():
    response = client.post("/analyze", json={"text": "a" * 50_001})
    assert response.status_code == 400
    assert "50,000" in response.json()["detail"][0]


def test_rejects_invalid_provider():
    # Our global validation handler maps Pydantic errors to 400
    response = client.post("/analyze", json={"text": VALID_TEXT, "provider": "unknown_llm"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Provider error → correct HTTP status code
# ---------------------------------------------------------------------------

def test_rate_limit_returns_429():
    err = AIServiceError("Rate limit reached. Please try again shortly.", status_code=429)
    with patch("app.services.ai_service.get_provider") as mock_factory:
        mock_factory.return_value.analyze.side_effect = err
        response = client.post("/analyze", json={"text": VALID_TEXT})
    assert response.status_code == 429
    assert "Rate limit" in response.json()["detail"]


def test_connection_error_returns_502():
    err = AIServiceError("Could not reach the AI provider.", status_code=502)
    with patch("app.services.ai_service.get_provider") as mock_factory:
        mock_factory.return_value.analyze.side_effect = err
        response = client.post("/analyze", json={"text": VALID_TEXT})
    assert response.status_code == 502


def test_provider_status_error_returns_503():
    err = AIServiceError("AI provider returned an error (status 500).", status_code=503)
    with patch("app.services.ai_service.get_provider") as mock_factory:
        mock_factory.return_value.analyze.side_effect = err
        response = client.post("/analyze", json={"text": VALID_TEXT})
    assert response.status_code == 503


def test_schema_error_returns_500():
    err = AISchemaError("Model response 'action_items' must be a list of exactly 3 items.")
    with patch("app.services.ai_service.get_provider") as mock_factory:
        mock_factory.return_value.analyze.side_effect = err
        response = client.post("/analyze", json={"text": VALID_TEXT})
    assert response.status_code == 500
    assert "action_items" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_auth_rejected_with_wrong_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-key")
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    import app.auth.dependencies as auth_dep
    importlib.reload(auth_dep)

    response = client.post(
        "/analyze",
        json={"text": VALID_TEXT},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# AnthropicProvider unit tests (test provider directly, no HTTP layer)
# ---------------------------------------------------------------------------

def test_provider_happy_path_with_tool_use():
    provider = AnthropicProvider()
    provider._client = MagicMock()
    provider._client.messages.create.return_value = make_tool_use_response(MOCK_VALID_RESULT)

    result = provider.analyze(VALID_TEXT)
    assert result["summary"] == "The text is a test."
    assert len(result["action_items"]) == 3


def test_provider_raises_schema_error_when_no_tool_block():
    provider = AnthropicProvider()
    mock_response = MagicMock()
    mock_response.content = []
    mock_response.id = "msg_test"
    provider._client = MagicMock()
    provider._client.messages.create.return_value = mock_response

    with pytest.raises(AISchemaError, match="tool_use"):
        provider.analyze(VALID_TEXT)


def test_provider_raises_schema_error_on_wrong_action_item_count():
    provider = AnthropicProvider()
    provider._client = MagicMock()
    provider._client.messages.create.return_value = make_tool_use_response(
        {"summary": "ok", "action_items": ["only one"]}
    )

    with pytest.raises(AISchemaError, match="exactly 3"):
        provider.analyze(VALID_TEXT)


def test_provider_logs_request_metadata(caplog):
    provider = AnthropicProvider()
    provider._client = MagicMock()
    provider._client.messages.create.return_value = make_tool_use_response(MOCK_VALID_RESULT)

    with caplog.at_level(logging.INFO, logger="app.providers.anthropic_provider"):
        provider.analyze(VALID_TEXT)

    log_text = " ".join(r.message for r in caplog.records)
    assert "provider=anthropic" in log_text
    assert "model=" in log_text
    assert "elapsed_ms=" in log_text
    assert "request_id=" in log_text


def _make_rate_limit_error() -> anthropic.RateLimitError:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(429, request=req)
    return anthropic.RateLimitError("rate limited", response=resp, body={})


def test_provider_retries_once_on_rate_limit():
    provider = AnthropicProvider()
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = [
        _make_rate_limit_error(),
        make_tool_use_response(MOCK_VALID_RESULT),
    ]

    result = provider.analyze(VALID_TEXT)
    assert result["summary"] == "The text is a test."
    assert provider._client.messages.create.call_count == 2


def test_provider_raises_429_after_all_retries_exhausted():
    provider = AnthropicProvider()
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = [
        _make_rate_limit_error(),
        _make_rate_limit_error(),
    ]

    with pytest.raises(AIServiceError) as exc_info:
        provider.analyze(VALID_TEXT)
    assert exc_info.value.status_code == 429

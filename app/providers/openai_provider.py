import json
import logging
import time

import openai

from app.config import MAX_RETRIES, OPENAI_MODEL, TIMEOUT_SECONDS, get_api_key
from app.providers.base import AISchemaError, AIServiceError, BaseProvider

logger = logging.getLogger(__name__)

ANALYSIS_FUNCTION = {
    "name": "analyze_text",
    "description": "Return a structured analysis of the provided text.",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A 2–3 sentence summary of the key points.",
            },
            "action_items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exactly 3 concise, actionable strings derived from the text.",
            },
        },
        "required": ["summary", "action_items"],
    },
}


class OpenAIProvider(BaseProvider):
    def __init__(self) -> None:
        self._client: openai.OpenAI | None = None

    @property
    def client(self) -> openai.OpenAI:
        if self._client is None:
            self._client = openai.OpenAI(
                api_key=get_api_key("openai"),
                timeout=TIMEOUT_SECONDS,
            )
        return self._client

    def analyze(self, text: str) -> dict:
        retryable = (openai.RateLimitError, openai.APIConnectionError)
        last_error: AIServiceError | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            start = time.monotonic()
            try:
                response = self.client.chat.completions.create(
                    model=OPENAI_MODEL,
                    tools=[{"type": "function", "function": ANALYSIS_FUNCTION}],
                    tool_choice={"type": "function", "function": {"name": "analyze_text"}},
                    messages=[
                        {"role": "user", "content": f"Analyze the following text:\n\n{text}"}
                    ],
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)
                request_id = response.id
                logger.info(
                    "provider=openai model=%s request_id=%s elapsed_ms=%d attempt=%d",
                    OPENAI_MODEL,
                    request_id,
                    elapsed_ms,
                    attempt,
                )
                tool_call = next(
                    (
                        tc
                        for tc in (response.choices[0].message.tool_calls or [])
                        if tc.function.name == "analyze_text"
                    ),
                    None,
                )
                if tool_call is None:
                    raise AISchemaError("Model did not return a structured function_call response.")
                parsed = json.loads(tool_call.function.arguments)
                return _validate(parsed)

            except retryable as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                status = 429 if isinstance(e, openai.RateLimitError) else 502
                msg = (
                    "Rate limit reached. Please try again shortly."
                    if status == 429
                    else "Could not reach the AI provider."
                )
                logger.warning(
                    "provider=openai attempt=%d/%d retryable_error=%s status=%d elapsed_ms=%d",
                    attempt,
                    MAX_RETRIES,
                    type(e).__name__,
                    status,
                    elapsed_ms,
                )
                last_error = AIServiceError(msg, status_code=status)

            except openai.APIStatusError as e:
                logger.error("provider=openai api_status=%d", e.status_code)
                raise AIServiceError(
                    f"AI provider returned an error (status {e.status_code}).",
                    status_code=503,
                ) from e

        assert last_error is not None
        raise last_error


def _validate(parsed: dict) -> dict:
    if not isinstance(parsed.get("summary"), str) or not parsed["summary"].strip():
        raise AISchemaError("Model response 'summary' must be a non-empty string.")
    items = parsed.get("action_items", [])
    if not isinstance(items, list) or len(items) != 3:
        raise AISchemaError("Model response 'action_items' must be a list of exactly 3 items.")
    if not all(isinstance(i, str) and i.strip() for i in items):
        raise AISchemaError("Each action item must be a non-empty string.")
    return parsed

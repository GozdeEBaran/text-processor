import time
import logging
from abc import ABC, abstractmethod
import anthropic

from config import MODEL_NAME, MAX_RETRIES, TIMEOUT_SECONDS, get_api_key

logger = logging.getLogger(__name__)

# Schema-constrained tool forces the model to return valid, typed JSON —
# no prompt-only parsing, no json.loads, no markdown-fence stripping.
ANALYSIS_TOOL = {
    "name": "analyze_text",
    "description": "Return a structured analysis of the provided text.",
    "input_schema": {
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


class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class AISchemaError(AIServiceError):
    pass


class BaseProvider(ABC):
    @abstractmethod
    def analyze(self, text: str) -> dict: ...


class AnthropicProvider(BaseProvider):
    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=get_api_key("anthropic"),
                timeout=TIMEOUT_SECONDS,
            )
        return self._client

    def analyze(self, text: str) -> dict:
        retryable = (anthropic.RateLimitError, anthropic.APIConnectionError)
        last_error: AIServiceError | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            start = time.monotonic()
            try:
                message = self.client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=512,
                    tools=[ANALYSIS_TOOL],
                    tool_choice={"type": "tool", "name": "analyze_text"},
                    messages=[
                        {"role": "user", "content": f"Analyze the following text:\n\n{text}"}
                    ],
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)
                request_id = getattr(message, "_request_id", None) or message.id
                logger.info(
                    "provider=anthropic model=%s request_id=%s elapsed_ms=%d attempt=%d",
                    MODEL_NAME,
                    request_id,
                    elapsed_ms,
                    attempt,
                )
                tool_block = next(
                    (b for b in message.content if b.type == "tool_use"), None
                )
                if tool_block is None:
                    raise AISchemaError("Model did not return a structured tool_use response.")
                return _validate(tool_block.input)

            except retryable as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                status = 429 if isinstance(e, anthropic.RateLimitError) else 502
                msg = (
                    "Rate limit reached. Please try again shortly."
                    if status == 429
                    else "Could not reach the AI provider."
                )
                logger.warning(
                    "provider=anthropic attempt=%d/%d retryable_error=%s status=%d elapsed_ms=%d",
                    attempt,
                    MAX_RETRIES,
                    type(e).__name__,
                    status,
                    elapsed_ms,
                )
                last_error = AIServiceError(msg, status_code=status)

            except anthropic.APIStatusError as e:
                logger.error(
                    "provider=anthropic api_status=%d",
                    e.status_code,
                )
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

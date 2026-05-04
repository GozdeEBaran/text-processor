# Text Processor API

FastAPI service that takes a block of text and returns a summary plus 3 action items as JSON, backed by Claude or GPT-4o.

## Run it

With Docker:
```bash
cp .env.example .env   # fill in your API key(s)
docker compose up --build
```

Without Docker:
```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

API is at `http://localhost:8000`, interactive docs at `/docs`.

## Usage

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text here, at least 20 characters."}'
```

To use OpenAI instead of Anthropic:
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text here.", "provider": "openai"}'
```

Response:
```json
{
  "summary": "The text discusses...",
  "action_items": ["Do X", "Review Y", "Follow up on Z"],
  "model": "claude-sonnet-4-20250514",
  "provider": "anthropic",
  "input_length": 67
}
```

If `API_KEY` is set in `.env`, pass it on every request:
```
X-API-Key: your-key
```

## Project structure

```
app/
├── main.py                    # app setup, error handlers
├── config.py                  # env vars, provider/model selection
├── models/schemas.py          # request & response types
├── providers/
│   ├── base.py                # BaseProvider, shared error classes
│   ├── anthropic_provider.py  # Claude via tool_use
│   └── openai_provider.py     # GPT-4o via function calling
├── routes/
│   ├── analyze.py             # POST /analyze
│   └── health.py              # GET /healthz
├── services/ai_service.py     # calls the provider factory
└── auth/dependencies.py       # X-API-Key guard
tests/
```

## What I built and why

`POST /analyze` validates the input, picks a provider (from the request body or the `PROVIDER` env var), and returns structured JSON. Both providers use their tool/function-calling APIs rather than prompt parsing — the output schema is enforced at the API level, so there's no `json.loads` on raw text and no string manipulation to clean up the response.

Input validation is Pydantic: 20 character minimum, 50,000 character maximum. Both limits are intentional. Too-short inputs produce meaningless output. No upper bound means a single request could push a lot of tokens through without the caller realizing it.

Auth is opt-in. If `API_KEY` isn't in the environment, `/analyze` is open. Makes local dev easier without needing a workaround.

I went with FastAPI over Flask because the automatic OpenAPI docs and native Pydantic integration actually matter when the whole point is a well-defined request/response contract. `/docs` reflecting the real types is useful, not just a checkbox.

## What didn't work at first

The first version used a system prompt to get structured JSON from Claude. It worked most of the time — which isn't good enough when the next line is `json.loads`. Markdown fences would sneak through, action item counts would drift to 2 or 4, and formatting would vary between model versions.

Switching to tool_use (Anthropic) and function calling (OpenAI) fixed all of it. The schema is declared once, the model is forced to match it, and there's nothing left to parse or clean up.

## What I'd add with more time

**Async job queue** — every request is currently synchronous and hits the provider API directly. Under any real load that's a problem: rate limits stack up, clients sit waiting on slow responses, and there's no clean retry path. The right fix is an SQS-backed queue with a `GET /result/{job_id}` polling endpoint. I've used this pattern for async AI pipelines before and it holds up well.

**Streaming** — both providers support streamed responses and FastAPI handles it natively with `StreamingResponse`. For longer inputs the perceived latency is much better on the client side.

**Input chunking** — right now the full text goes in one API call. For anything long that hits context limits fast. The standard approach is chunk, summarize each piece, then summarize the summaries.

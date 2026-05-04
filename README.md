# Text Processor API

A FastAPI service that takes a block of text, sends it to Claude, and returns a summary + 3 action items as structured JSON.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env # add your key
uvicorn main:app --reload
```

API runs at http://localhost:8000 — interactive docs at /docs.

## Usage

```bash
curl -X POST http://localhost:8000/analyze \
 -H "Content-Type: application/json" \
 -d '{"text": "Your text here, must be at least 20 characters."}'
```

Response:

```json
{
  "summary": "The text discusses...",
  "action_items": ["Do X", "Review Y", "Follow up on Z"],
  "model": "claude-sonnet-4-20250514",
  "input_length": 67
}
```

## What I Built

FastAPI backend with a single POST /analyze endpoint. Pydantic handles request validation, the Anthropic SDK calls Claude, and the response comes back as typed JSON. Kept it intentionally simple, no database, no auth, just the core flow working cleanly. Used FastAPI since it's what I've been building with in production lately, felt like the right fit over Flask for the automatic docs and typed request handling.

## The Prompt

I put the format instructions in the system prompt rather than the user message, and led with the constraint ("respond with ONLY valid JSON") before anything else. My first instinct was to describe the fields and trust the model — that didn't work well, kept getting loose formatting. Adding an explicit one-line example at the end of the prompt was what actually locked in the structure consistently.

## What Didn't Work at First

Two things bit me early:

First, the model kept returning markdown-wrapped JSON even with instructions not to, the ```json fences were showing up and breaking json.loads. Moving the "no markdown" line to the very top of the system prompt helped a lot. I also left a defensive strip in ai_service.py that removes fences if they still sneak through, costs nothing and protects against the model drifting between versions.

Second, action_items was coming back with 2 or 4 items pretty often. Changing "three" to "exactly 3" (the numeral) and adding the example line fixed it. Not sure why the numeral works better but it does.

## What I'd Improve With More Time

A few things I thought about but didn't build:

Async queue for heavy load - right now every request hits the Anthropic API directly and synchronously. At any real scale that would blow through rate limits fast. I'd push requests into SQS and have the client poll a /result/{job_id} endpoint. I used this pattern at Goldenfinch for an async AI pipeline and it holds up well.

Streaming — Claude supports streamed responses and FastAPI handles it natively with StreamingResponse. For longer inputs the latency would feel much better to callers.

Input chunking — the current approach sends the full text in one shot. For anything long I'd chunk it, summarize each piece, then summarize the summaries. Fine for this task size, would matter quickly in production.

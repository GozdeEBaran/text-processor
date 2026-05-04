import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from models import AnalyzeRequest, AnalyzeResponse
from ai_service import analyze_text, AIServiceError
from config import MODEL_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="Text Processor API",
    description="Summarizes text and extracts action items using Claude.",
    version="1.0.0",
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: Exception):
    errors = exc.errors() if hasattr(exc, "errors") else []
    messages = [err["msg"] for err in errors]
    return JSONResponse(status_code=400, content={"detail": messages})


@app.exception_handler(AIServiceError)
async def ai_service_error_handler(request: Request, exc: AIServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    result = analyze_text(request.text)

    return AnalyzeResponse(
        summary=result["summary"],
        action_items=result["action_items"],
        model=MODEL_NAME,
        input_length=len(request.text),
    )

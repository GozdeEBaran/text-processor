import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.providers.base import AIServiceError
from app.routes.analyze import router as analyze_router
from app.routes.health import router as health_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="Text Processor API",
    description="Summarizes text and extracts action items using Claude or OpenAI.",
    version="2.0.0",
)

app.include_router(health_router)
app.include_router(analyze_router)


@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: Exception):
    errors = exc.errors() if hasattr(exc, "errors") else []
    messages = [err["msg"] for err in errors]
    return JSONResponse(status_code=400, content={"detail": messages})


@app.exception_handler(AIServiceError)
async def ai_service_error_handler(request: Request, exc: AIServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

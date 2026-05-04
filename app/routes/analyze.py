from fastapi import APIRouter, Depends

from app.auth.dependencies import require_api_key
from app.config import PRIMARY_PROVIDER, get_model_name
from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.ai_service import analyze_text

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_api_key)])
def analyze(request: AnalyzeRequest):
    provider_name = request.provider or PRIMARY_PROVIDER
    result = analyze_text(request.text, provider_name)
    return AnalyzeResponse(
        summary=result["summary"],
        action_items=result["action_items"],
        model=get_model_name(provider_name),
        provider=provider_name,
        input_length=len(request.text),
    )

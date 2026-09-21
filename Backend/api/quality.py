"""
FastAPI Router for Quality Evaluation (/api/quality-check)
"""

from fastapi import APIRouter
from backend.engine.quality import evaluate_quality
from backend.models.api_models import QualityCheckRequest, QualityCheckResponse

router = APIRouter(tags=["Quality Gate"])


@router.post("/api/quality-check", response_model=QualityCheckResponse)
def quality_check(payload: QualityCheckRequest):
    """Evaluates node execution output against Quality Gate threshold."""
    result = evaluate_quality(
        node=payload.node,
        output=payload.output,
        required_quality=payload.required_quality,
    )
    return result

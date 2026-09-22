"""
Quality Evaluation API Router.
"""

from fastapi import APIRouter, status
from backend.models.api_models import QualityCheckRequest, QualityCheckResponse
from backend.engine.quality import evaluate_quality

router = APIRouter(prefix="/api/quality-check", tags=["Quality Gate"])


@router.post("", response_model=QualityCheckResponse)
def check_quality(payload: QualityCheckRequest):
    """
    Evaluates node quality score against required quality threshold.

    Returns PASS or ESCALATE action.
    """
    res = evaluate_quality(
        node=payload.node,
        output=payload.output,
        required_quality=payload.required_quality,
        seed=payload.seed
    )
    return QualityCheckResponse(**res)

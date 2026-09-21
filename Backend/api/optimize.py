"""
FastAPI Router for Workflow Optimization (/api/optimize)
"""

from datetime import datetime, timezone
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status

from backend.db.database import get_db_session
from backend.db.repository import PlanRepository, WorkflowRepository
from backend.engine.optimizer import optimize_workflow
from backend.models.api_models import OptimizeRequest, OptimizeResponse

router = APIRouter(prefix="/api/optimize", tags=["Optimization"])


@router.post("", response_model=OptimizeResponse)
def optimize(payload: OptimizeRequest, db: sqlite3.Connection = Depends(get_db_session)):
    """
    Optimizes a workflow DAG across Carbon, Latency, Cost, and Quality constraints.

    Can be called repeatedly with different priority weights for What-If scenario analysis.
    """
    workflow = WorkflowRepository.get_workflow(db, payload.workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{payload.workflow_id}' not found.",
        )

    try:
        opt_res = optimize_workflow(
            workflow_data=workflow,
            carbon_budget=payload.carbon_budget,
            deadline_seconds=payload.deadline_seconds,
            quality_requirement=payload.quality_requirement,
            carbon_weight=payload.carbon_weight,
            latency_weight=payload.latency_weight,
            cost_weight=payload.cost_weight,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Optimization failed: {str(err)}",
        )

    created_at = datetime.now(timezone.utc).isoformat()

    saved_plan = PlanRepository.save_plan(
        conn=db,
        plan_id=opt_res["plan_id"],
        workflow_id=payload.workflow_id,
        baseline=opt_res["baseline"],
        optimized=opt_res["optimized"],
        savings=opt_res["savings"],
        reasoning=opt_res["reasoning"],
        created_at=created_at,
    )

    return saved_plan

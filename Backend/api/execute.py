"""
FastAPI Router for Plan Execution Simulation (/api/execute)
"""

from datetime import datetime, timezone
import sqlite3
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.db.database import get_db_session
from backend.db.repository import ExecutionRepository, PlanRepository
from backend.engine.simulator import execute_plan
from backend.models.api_models import ExecuteRequest, ExecuteResponse

router = APIRouter(prefix="/api/execute", tags=["Execution"])


@router.post("/{plan_id}", response_model=ExecuteResponse)
def execute_by_id(
    plan_id: str,
    payload: Optional[ExecuteRequest] = None,
    db: sqlite3.Connection = Depends(get_db_session),
):
    """Executes a saved execution plan using the CarbonPilot simulation engine."""
    plan = PlanRepository.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution plan with ID '{plan_id}' not found.",
        )

    random_seed = payload.random_seed if payload else None
    forced_fails = payload.force_quality_fail_nodes if payload else None

    sim_res = execute_plan(
        plan=plan["optimized"],
        random_seed=random_seed,
        force_quality_fail_nodes=forced_fails,
    )

    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    executed_at = datetime.now(timezone.utc).isoformat()

    saved_exec = ExecutionRepository.save_execution(
        conn=db,
        execution_id=execution_id,
        plan_id=plan_id,
        workflow_id=plan["workflow_id"],
        status=sim_res["status"],
        total_carbon=sim_res["total_actual_carbon"],
        total_cost=sim_res["total_actual_cost"],
        total_latency=sim_res["total_actual_latency"],
        final_quality=sim_res["final_quality"],
        node_results=sim_res["node_results"],
        escalations=sim_res["escalations"],
        executed_at=executed_at,
    )

    return saved_exec


@router.post("", response_model=ExecuteResponse)
def execute_body(payload: ExecuteRequest, db: sqlite3.Connection = Depends(get_db_session)):
    """Executes a plan where plan_id is provided in the request body."""
    if not payload.plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="plan_id must be provided in request body when invoking POST /api/execute",
        )
    return execute_by_id(plan_id=payload.plan_id, payload=payload, db=db)

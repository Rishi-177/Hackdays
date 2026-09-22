"""
Execution API Router (Simulated Plan Execution).
"""

import uuid
from fastapi import APIRouter, HTTPException, status, Body
from typing import Optional
from models.api_models import ExecuteRequest, ExecuteResponse
from db.repository import get_execution_plan, save_execution
from engine.simulator import execute_plan

router = APIRouter(prefix="/api/execute", tags=["Execution"])


@router.post("/{plan_id}", response_model=ExecuteResponse)
def execute_execution_plan(
    plan_id: str,
    payload: Optional[ExecuteRequest] = Body(default_factory=ExecuteRequest)
):
    """
    Simulates execution of a generated plan by plan_id.

    Calculates predicted vs actual metrics, runs Quality Gate evaluations, handles
    automated model escalations on failure, and stores execution run logs.
    """
    saved_plan = get_execution_plan(plan_id)
    if not saved_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution plan with ID '{plan_id}' not found. Please run POST /api/optimize first."
        )

    # Extract target plan structure for simulator
    optimized_plan = saved_plan.get("optimized", {})
    workflow_id = saved_plan.get("workflow_id", "demo")

    seed = payload.seed if payload else 42
    forced_overrides = payload.forced_quality_overrides if payload else None

    # Execute simulation
    sim_result = execute_plan(
        plan=optimized_plan,
        seed=seed,
        forced_quality_overrides=forced_overrides
    )

    exec_id = f"exec_{uuid.uuid4().hex[:8]}"

    exec_record = {
        "id": exec_id,
        "execution_id": exec_id,
        "plan_id": plan_id,
        "workflow_id": workflow_id,
        "status": sim_result["status"],
        "total_actual_carbon": sim_result["total_actual_carbon"],
        "total_actual_cost": sim_result["total_actual_cost"],
        "total_actual_latency": sim_result["total_actual_latency"],
        "final_quality": sim_result["final_quality"],
        "node_results": sim_result["node_results"],
        "escalations": sim_result["escalations"]
    }

    save_execution(exec_record)

    return ExecuteResponse(**exec_record)

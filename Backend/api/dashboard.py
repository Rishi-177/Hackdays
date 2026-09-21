"""
FastAPI Router for Comparison Dashboard (/api/dashboard/{workflow_id})
"""

import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status

from backend.db.database import get_db_session
from backend.db.repository import ExecutionRepository, PlanRepository, WorkflowRepository
from backend.models.api_models import DashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/{workflow_id}", response_model=DashboardResponse)
def get_dashboard(workflow_id: str, db: sqlite3.Connection = Depends(get_db_session)):
    """
    Returns aggregated dashboard comparison data for a workflow:
    Baseline vs CarbonPilot metrics, carbon/cost/latency savings, node DAG info, and execution history.
    """
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    latest_plan = PlanRepository.get_latest_plan_for_workflow(db, workflow_id)
    executions = ExecutionRepository.get_executions_for_workflow(db, workflow_id)

    if latest_plan:
        baseline_metrics = latest_plan["baseline"]
        carbonpilot_metrics = latest_plan["optimized"]
        savings = latest_plan["savings"]
        node_info = latest_plan["optimized"]["nodes"]
    else:
        # Default fallback metrics if no plan generated yet
        nodes = workflow["nodes"]
        baseline_metrics = {"carbon": 0.0, "cost": 0.0, "latency": 0.0, "quality": 0.0, "ai_calls": len(nodes)}
        carbonpilot_metrics = {"carbon": 0.0, "cost": 0.0, "latency": 0.0, "quality": 0.0, "ai_calls": len(nodes)}
        savings = {"carbon_percent": 0.0, "cost_percent": 0.0, "latency_percent": 0.0, "carbon_saved_g": 0.0, "cost_saved_usd": 0.0, "time_saved_sec": 0.0}
        node_info = nodes

    return {
        "workflow_id": workflow["workflow_id"],
        "workflow_name": workflow["name"],
        "baseline_metrics": baseline_metrics,
        "carbonpilot_metrics": carbonpilot_metrics,
        "savings": savings,
        "node_information": node_info,
        "execution_history": executions,
    }

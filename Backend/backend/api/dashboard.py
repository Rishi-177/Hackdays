"""
Dashboard Metrics & Comparison API Router.
"""

from fastapi import APIRouter, HTTPException, status
from backend.models.api_models import DashboardResponse, SavingsMetrics
from backend.db.repository import get_latest_execution_plan_by_workflow, get_executions_by_workflow, get_workflow, DEMO_WORKFLOW
from backend.engine.optimizer import optimize_workflow

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/{workflow_id}", response_model=DashboardResponse)
def get_dashboard_metrics(workflow_id: str):
    """
    Retrieves baseline vs CarbonPilot optimization metrics, savings comparisons,
    node configuration details, and historical execution runs for a given workflow.
    """
    wf = get_workflow(workflow_id)
    if not wf:
        wf = DEMO_WORKFLOW

    # Get latest plan or generate default optimized plan for demo visualization
    latest_plan = get_latest_execution_plan_by_workflow(workflow_id)
    if not latest_plan:
        opt_res = optimize_workflow(workflow=wf.get("dag"))
        baseline = opt_res["baseline"]
        optimized = opt_res["optimized"]
        savings = opt_res["savings"]
    else:
        baseline = latest_plan.get("baseline", {})
        optimized = latest_plan.get("optimized", {})
        savings = latest_plan.get("savings", {})

    executions = get_executions_by_workflow(workflow_id)

    nodes_info = optimized.get("nodes", wf.get("dag", {}).get("nodes", []))

    return DashboardResponse(
        workflow_id=workflow_id,
        baseline=baseline,
        optimized=optimized,
        savings=SavingsMetrics(**savings),
        nodes=nodes_info,
        execution_history=executions
    )

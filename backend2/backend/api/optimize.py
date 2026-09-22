"""
Optimization API Router (Whole-Workflow Optimizer & What-If Engine).
"""

import uuid
from fastapi import APIRouter, HTTPException, status
from models.api_models import OptimizeRequest, OptimizeResponse, SavingsMetrics
from db.repository import get_workflow, save_execution_plan, DEMO_WORKFLOW
from engine.optimizer import optimize_workflow

router = APIRouter(prefix="/api/optimize", tags=["Optimization"])


@router.post("", response_model=OptimizeResponse)
def optimize(payload: OptimizeRequest):
    """
    Whole-Workflow Optimization Endpoint.

    Analyzes DAG workflow dependencies, enforces hard constraints (Carbon Budget, Deadline, Quality),
    generates baseline vs CarbonPilot candidate execution plans, calculates savings percentages,
    and returns human-explainable decision reasoning.
    """
    workflow_id = payload.workflow_id or "demo"

    # 1. Load workflow DAG
    if payload.workflow_dag:
        dag = payload.workflow_dag
    else:
        wf = get_workflow(workflow_id)
        if not wf:
            wf = DEMO_WORKFLOW
        dag = wf.get("dag", DEMO_WORKFLOW["dag"])

    # 2. Call Whole-Workflow Optimizer Engine
    opt_result = optimize_workflow(
        workflow_dag=dag,
        carbon_budget=payload.carbon_budget,
        deadline_seconds=payload.deadline_seconds,
        quality_requirement=payload.quality_requirement,
        carbon_weight=payload.carbon_weight,
        latency_weight=payload.latency_weight,
        cost_weight=payload.cost_weight
    )

    plan_id = f"plan_{uuid.uuid4().hex[:8]}"

    plan_record = {
        "id": plan_id,
        "plan_id": plan_id,
        "workflow_id": workflow_id,
        "baseline": opt_result["baseline"],
        "optimized": opt_result["optimized"],
        "savings": opt_result["savings"],
        "reasoning": opt_result["reasoning"]
    }

    # 3. Persist execution plan for execution endpoint
    save_execution_plan(plan_record)

    return OptimizeResponse(
        plan_id=plan_id,
        workflow_id=workflow_id,
        baseline=opt_result["baseline"],
        optimized=opt_result["optimized"],
        savings=SavingsMetrics(**opt_result["savings"]),
        reasoning=opt_result["reasoning"]
    )

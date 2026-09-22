"""
CarbonPilot Engine Package
"""

from backend.engine.dag import WorkflowDAG, validate_dag, get_critical_path_depth
from backend.engine.carbon import (
    calculate_node_carbon,
    calculate_node_latency,
    calculate_node_cost,
    calculate_total_carbon,
    check_carbon_budget,
    calculate_slack,
    estimate_node_metrics,
)
from backend.engine.optimizer import optimize_workflow, compute_workflow_metrics
from backend.engine.scheduler import create_execution_plan, generate_candidate_plans
from backend.engine.quality import evaluate_quality, select_escalation_model
from backend.engine.simulator import execute_plan, MODEL_PROFILES, REGION_PROFILES

__all__ = [
    "WorkflowDAG",
    "validate_dag",
    "get_critical_path_depth",
    "calculate_node_carbon",
    "calculate_node_latency",
    "calculate_node_cost",
    "calculate_total_carbon",
    "check_carbon_budget",
    "calculate_slack",
    "estimate_node_metrics",
    "optimize_workflow",
    "compute_workflow_metrics",
    "create_execution_plan",
    "generate_candidate_plans",
    "evaluate_quality",
    "select_escalation_model",
    "execute_plan",
    "MODEL_PROFILES",
    "REGION_PROFILES",
]

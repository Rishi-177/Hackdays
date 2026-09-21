"""Engine package for CarbonPilot DAG, Optimizer, Carbon, and Scheduler."""

from backend.engine.carbon import (
    calculate_node_carbon,
    calculate_node_cost,
    calculate_node_latency,
    calculate_slack,
    calculate_total_carbon,
    check_carbon_budget,
    load_model_profiles,
    load_region_profiles,
)
from backend.engine.dag import (
    CycleError,
    DAGValidationError,
    WorkflowDAG,
)
from backend.engine.optimizer import (
    compute_workflow_metrics,
    optimize_workflow,
)
from backend.engine.scheduler import (
    CandidatePlan,
    NodeAssignment,
    create_execution_plan,
    generate_candidate_plans,
)

__all__ = [
    "WorkflowDAG",
    "DAGValidationError",
    "CycleError",
    "compute_workflow_metrics",
    "optimize_workflow",
    "calculate_node_carbon",
    "calculate_node_latency",
    "calculate_node_cost",
    "calculate_total_carbon",
    "check_carbon_budget",
    "calculate_slack",
    "load_model_profiles",
    "load_region_profiles",
    "create_execution_plan",
    "generate_candidate_plans",
    "CandidatePlan",
    "NodeAssignment",
]

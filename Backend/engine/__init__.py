"""
CarbonPilot Engine Package.
Exposes Quality Gate, Smart Escalation, Execution Simulator, DAG, Carbon, Scheduler, and Optimizer functions.
"""

from backend.engine.carbon import calculate_node_carbon, calculate_workflow_carbon
from backend.engine.dag import topological_sort, validate_dag
from backend.engine.optimizer import create_execution_plan, optimize_workflow
from backend.engine.quality import (
    MODEL_HIERARCHY,
    MODEL_PROFILES,
    calculate_escalation_deltas,
    evaluate_quality,
    select_escalation_model,
)
from backend.engine.scheduler import calculate_deadline_slack, evaluate_slack_scheduling
from backend.engine.simulator import REGION_PROFILES, execute_plan

__all__ = [
    "MODEL_PROFILES",
    "MODEL_HIERARCHY",
    "REGION_PROFILES",
    "evaluate_quality",
    "select_escalation_model",
    "calculate_escalation_deltas",
    "execute_plan",
    "validate_dag",
    "topological_sort",
    "calculate_node_carbon",
    "calculate_workflow_carbon",
    "calculate_deadline_slack",
    "evaluate_slack_scheduling",
    "optimize_workflow",
    "create_execution_plan",
]

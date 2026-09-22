"""
Execution Simulator Module for CarbonPilot.

Simulates workflow execution with controlled variance, Quality Gate checks,
and Smart Model Escalation.
"""

import random
from typing import Any, Dict, List, Optional, Union
from engine.quality import evaluate_quality, select_escalation_model, DEFAULT_MODEL_HIERARCHY

# Default Model Profiles for Hackathon Simulation
MODEL_PROFILES: Dict[str, Dict[str, Any]] = {
    "EfficientModel": {
        "cost": 0.002,          # USD per node
        "carbon": 10.0,         # g CO2e per node
        "latency": 2.0,         # seconds
        "quality_base": 0.85,   # base quality score
    },
    "BalancedModel": {
        "cost": 0.010,
        "carbon": 25.0,
        "latency": 4.0,
        "quality_base": 0.92,
    },
    "AdvancedModel": {
        "cost": 0.040,
        "carbon": 60.0,
        "latency": 8.0,
        "quality_base": 0.98,
    },
}

# Default Region Profiles for Hackathon Simulation
REGION_PROFILES: Dict[str, Dict[str, float]] = {
    "Region-A": {
        "carbon_mult": 1.4,     # High carbon
        "latency_mult": 0.85,   # Low latency
    },
    "Region-B": {
        "carbon_mult": 0.7,     # Low carbon
        "latency_mult": 1.0,    # Medium latency
    },
    "Region-C": {
        "carbon_mult": 1.0,     # Medium carbon
        "latency_mult": 0.9,    # Medium/low latency
    },
}


def _get_model_metrics(model_name: str) -> Dict[str, Any]:
    """Retrieve default model metrics or fallback to BalancedModel values."""
    for key, metrics in MODEL_PROFILES.items():
        if key.lower() in model_name.lower() or model_name.lower() in key.lower():
            return metrics
    return MODEL_PROFILES["BalancedModel"]


def _get_region_metrics(region_name: str) -> Dict[str, float]:
    """Retrieve region multipliers or fallback to default multipliers."""
    for key, metrics in REGION_PROFILES.items():
        if key.lower() in region_name.lower() or region_name.lower() in key.lower():
            return metrics
    return {"carbon_mult": 1.0, "latency_mult": 1.0}


def execute_plan(
    plan: Union[Dict[str, Any], List[Dict[str, Any]]],
    seed: Optional[int] = None,
    forced_quality_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Simulates execution of a workflow execution plan.

    Parameters:
        plan: Execution plan dictionary (containing 'nodes', 'execution_plan', or a list of node dicts).
        seed: Optional integer seed for deterministic controlled variance.
        forced_quality_overrides: Optional dict mapping node_id -> forced quality score (for demo scenarios).

    Returns:
        Dict matching specified return schema:
        {
            "status": "completed",
            "node_results": [...],
            "total_actual_carbon": float,
            "total_actual_cost": float,
            "total_actual_latency": float,
            "final_quality": float,
            "escalations": [...]
        }
    """
    # 1. Normalize plan structure into a list of node dicts
    nodes: List[Dict[str, Any]] = []
    if isinstance(plan, list):
        nodes = plan
    elif isinstance(plan, dict):
        if "nodes" in plan:
            nodes = plan["nodes"]
        elif "execution_plan" in plan and isinstance(plan["execution_plan"], dict) and "nodes" in plan["execution_plan"]:
            nodes = plan["execution_plan"]["nodes"]
        elif "execution_plan" in plan and isinstance(plan["execution_plan"], list):
            nodes = plan["execution_plan"]
        elif "workflow_dag" in plan and isinstance(plan["workflow_dag"], dict) and "nodes" in plan["workflow_dag"]:
            nodes = plan["workflow_dag"]["nodes"]
        elif "dag" in plan and isinstance(plan["dag"], dict) and "nodes" in plan["dag"]:
            nodes = plan["dag"]["nodes"]
        else:
            # Single node dict or direct dict wrapper
            nodes = [plan]

    # Initialize random number generator for controlled variation
    rng = random.Random(seed) if seed is not None else random.Random()

    node_results: List[Dict[str, Any]] = []
    escalations: List[Dict[str, Any]] = []

    total_actual_carbon = 0.0
    total_actual_cost = 0.0
    total_actual_latency = 0.0
    quality_scores: List[float] = []

    forced_overrides = forced_quality_overrides or {}

    for idx, node in enumerate(nodes):
        node_id = str(node.get("node_id", node.get("id", f"node_{idx}")))
        model_name = str(node.get("model", "EfficientModel"))
        region_name = str(node.get("region", "Region-B"))
        required_quality = float(node.get("required_quality", plan.get("required_quality", 0.90) if isinstance(plan, dict) else 0.90))

        model_metrics = _get_model_metrics(model_name)
        region_metrics = _get_region_metrics(region_name)

        # Baseline predicted values
        pred_latency = float(node.get("predicted_latency", model_metrics["latency"] * region_metrics["latency_mult"]))
        pred_carbon = float(node.get("predicted_carbon", model_metrics["carbon"] * region_metrics["carbon_mult"]))
        pred_cost = float(node.get("predicted_cost", model_metrics["cost"]))

        # Controlled variation between predicted and actual values (+/- 5% to 10%)
        var_lat = rng.uniform(0.95, 1.10)
        var_carb = rng.uniform(0.95, 1.08)
        var_cost = rng.uniform(0.98, 1.02)

        actual_latency = round(pred_latency * var_lat, 3)
        actual_carbon = round(pred_carbon * var_carb, 3)
        actual_cost = round(pred_cost * var_cost, 4)

        # Check if node or model specifies baseline quality
        if node_id in forced_overrides:
            initial_quality = float(forced_overrides[node_id])
        elif "quality" in node or "quality_score" in node:
            initial_quality = float(node.get("quality_score", node.get("quality")))
        else:
            base_q = model_metrics["quality_base"]
            initial_quality = round(max(0.0, min(1.0, base_q + rng.uniform(-0.02, 0.03))), 4)

        # Output mock object for Quality Gate evaluation
        output_data = {"quality_score": initial_quality, "result": f"Output from {node_id}"}
        eval_result = evaluate_quality(
            node={"node_id": node_id, "model": model_name},
            output=output_data,
            required_quality=required_quality,
            seed=seed
        )

        current_model = model_name
        original_model = model_name
        escalated = False
        num_escalations = 0

        additional_carbon = 0.0
        additional_cost = 0.0
        additional_latency = 0.0

        # Smart Model Escalation Loop if Quality Gate fails
        while not eval_result["passed"]:
            next_model = select_escalation_model(current_model)
            if not next_model:
                # No higher model available to escalate to
                break

            escalated = True
            num_escalations += 1
            next_model_name = str(next_model.get("name") if isinstance(next_model, dict) else next_model)
            
            # Metrics for escalated execution
            escalated_model_metrics = _get_model_metrics(next_model_name)
            esc_pred_lat = escalated_model_metrics["latency"] * region_metrics["latency_mult"]
            esc_pred_carb = escalated_model_metrics["carbon"] * region_metrics["carbon_mult"]
            esc_pred_cost = escalated_model_metrics["cost"]

            # Additional metrics added by running escalated model
            add_lat = round(esc_pred_lat * rng.uniform(0.95, 1.08), 3)
            add_carb = round(esc_pred_carb * rng.uniform(0.95, 1.05), 3)
            add_cost = round(esc_pred_cost * rng.uniform(0.98, 1.02), 4)

            additional_latency += add_lat
            additional_carbon += add_carb
            additional_cost += add_cost

            # Update actual node totals
            actual_latency = round(actual_latency + add_lat, 3)
            actual_carbon = round(actual_carbon + add_carb, 3)
            actual_cost = round(actual_cost + add_cost, 4)

            current_model = next_model_name

            # New quality score with escalated model
            new_quality = round(max(0.0, min(1.0, escalated_model_metrics["quality_base"] + rng.uniform(0.0, 0.02))), 4)
            output_data = {"quality_score": new_quality, "result": f"Escalated output from {node_id}"}
            
            eval_result = evaluate_quality(
                node={"node_id": node_id, "model": current_model},
                output=output_data,
                required_quality=required_quality,
                seed=seed
            )

        status = "ESCALATED" if escalated else "COMPLETED"

        if escalated:
            escalation_record = {
                "node_id": node_id,
                "original_model": original_model,
                "final_model": current_model,
                "number_of_escalations": num_escalations,
                "additional_carbon": round(additional_carbon, 3),
                "additional_cost": round(additional_cost, 4),
                "additional_latency": round(additional_latency, 3),
            }
            escalations.append(escalation_record)

        node_res = {
            "node_id": node_id,
            "model": current_model,
            "original_model": original_model,
            "region": region_name,
            "predicted_latency": pred_latency,
            "actual_latency": actual_latency,
            "predicted_carbon": pred_carbon,
            "actual_carbon": actual_carbon,
            "predicted_cost": pred_cost,
            "actual_cost": actual_cost,
            "quality": eval_result["quality_score"],
            "required_quality": required_quality,
            "status": status,
            "escalated": escalated
        }

        node_results.append(node_res)

        total_actual_carbon += actual_carbon
        total_actual_cost += actual_cost
        total_actual_latency += actual_latency
        quality_scores.append(eval_result["quality_score"])

    avg_final_quality = round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else 0.0

    return {
        "status": "completed",
        "node_results": node_results,
        "total_actual_carbon": round(total_actual_carbon, 3),
        "total_actual_cost": round(total_actual_cost, 4),
        "total_actual_latency": round(total_actual_latency, 3),
        "final_quality": avg_final_quality,
        "escalations": escalations
    }

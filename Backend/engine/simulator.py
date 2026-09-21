"""
CarbonPilot Execution Simulator Engine

Simulates DAG workflow execution with controlled variance, Quality Gate integration,
and Smart Model Escalation tracking.
"""

import random
from typing import Any, Dict, List, Optional, Set, Union

from backend.engine.quality import (
    MODEL_PROFILES,
    calculate_escalation_deltas,
    evaluate_quality,
    select_escalation_model,
)

# Standard region carbon and latency profiles
REGION_PROFILES: Dict[str, Dict[str, float]] = {
    "Region-A": {
        "carbon_factor": 1.4,
        "latency_factor": 0.85,
        "description": "High carbon, low latency",
    },
    "Region-B": {
        "carbon_factor": 0.65,
        "latency_factor": 1.25,
        "description": "Low carbon, medium latency",
    },
    "Region-C": {
        "carbon_factor": 1.0,
        "latency_factor": 1.0,
        "description": "Medium carbon, medium latency",
    },
}


def _get_node_predicted_metrics(node: Dict[str, Any]) -> Dict[str, float]:
    """Helper to extract or derive predicted latency, carbon, and cost for a node."""
    model_name = node.get("model", "EfficientModel")
    region_name = node.get("region", "Region-B")

    model_prof = MODEL_PROFILES.get(model_name, MODEL_PROFILES["EfficientModel"])
    region_prof = REGION_PROFILES.get(region_name, REGION_PROFILES["Region-B"])

    pred_lat = float(
        node.get(
            "predicted_latency",
            node.get("latency", model_prof["latency"] * region_prof["latency_factor"]),
        )
    )
    pred_carb = float(
        node.get(
            "predicted_carbon",
            node.get("carbon", model_prof["carbon"] * region_prof["carbon_factor"]),
        )
    )
    pred_cost = float(node.get("predicted_cost", node.get("cost", model_prof["cost"])))

    return {
        "predicted_latency": pred_lat,
        "predicted_carbon": pred_carb,
        "predicted_cost": pred_cost,
    }


def execute_plan(
    plan: Union[Dict[str, Any], List[Dict[str, Any]]],
    random_seed: Optional[int] = None,
    force_quality_fail_nodes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Simulates execution of an entire workflow plan DAG.

    Args:
        plan: Plan dictionary containing 'nodes' list/dict, or direct list of node dicts.
        random_seed: Optional seed for reproducible controlled variance.
        force_quality_fail_nodes: Optional list of node IDs to deliberately trigger Quality Gate failure & escalation.

    Returns:
        Dict formatted as:
        {
            "status": "completed",
            "node_results": [...],
            "total_actual_carbon": ...,
            "total_actual_cost": ...,
            "total_actual_latency": ...,
            "final_quality": ...,
            "escalations": [...]
        }
    """
    # 1. Normalize input plan nodes
    if isinstance(plan, dict):
        nodes_input = plan.get("nodes", [])
        if isinstance(nodes_input, dict):
            # Keyed by node_id
            nodes_list = []
            for nid, nval in nodes_input.items():
                ncopy = dict(nval)
                ncopy.setdefault("node_id", nid)
                nodes_list.append(ncopy)
        else:
            nodes_list = [dict(n) for n in nodes_input]
    else:
        nodes_list = [dict(n) for n in plan]

    # Initialize RNG if seed provided
    rng = random.Random(random_seed) if random_seed is not None else None
    forced_fails: Set[str] = set(force_quality_fail_nodes or [])

    node_results: List[Dict[str, Any]] = []
    all_escalations: List[Dict[str, Any]] = []

    # Map node_id -> finish times for DAG latency calculation
    actual_finish_times: Dict[str, float] = {}
    predicted_finish_times: Dict[str, float] = {}

    total_pred_carbon = 0.0
    total_pred_cost = 0.0
    total_act_carbon = 0.0
    total_act_cost = 0.0
    quality_scores: List[float] = []

    # 2. Iterate and simulate each node execution
    for node in nodes_list:
        node_id = str(node.get("node_id", node.get("id", f"node_{len(node_results)+1}")))
        model_name = str(node.get("model", "EfficientModel"))
        region_name = str(node.get("region", "Region-B"))
        required_quality = float(node.get("required_quality", 0.90))
        dependencies = list(node.get("dependencies", []))

        # Get base predicted metrics
        metrics = _get_node_predicted_metrics(node)
        pred_lat = metrics["predicted_latency"]
        pred_carb = metrics["predicted_carbon"]
        pred_cost = metrics["predicted_cost"]

        total_pred_carbon += pred_carb
        total_pred_cost += pred_cost

        # Calculate controlled variation (-3% to +8%)
        if rng is not None:
            var_lat = rng.uniform(-0.02, 0.10)
            var_carb = rng.uniform(-0.03, 0.08)
            var_cost = rng.uniform(-0.01, 0.05)
        else:
            # Fixed deterministic variance when no seed is passed
            var_lat = 0.05
            var_carb = 0.03
            var_cost = 0.02

        act_lat = round(pred_lat * (1.0 + var_lat), 2)
        act_carb = round(pred_carb * (1.0 + var_carb), 2)
        act_cost = round(pred_cost * (1.0 + var_cost), 4)

        # Base quality determination
        model_prof = MODEL_PROFILES.get(model_name, MODEL_PROFILES["EfficientModel"])
        if rng is not None:
            qual_jitter = rng.uniform(-0.015, 0.015)
        else:
            qual_jitter = 0.0

        current_quality = model_prof["quality"] + qual_jitter

        # Handle forced Quality Gate failure
        if node_id in forced_fails:
            current_quality = required_quality - 0.05

        current_model = model_name
        node_status = "COMPLETED"
        node_escalations: List[Dict[str, Any]] = []

        # Quality Gate Evaluation
        eval_res = evaluate_quality(
            node={"node_id": node_id, "model": current_model},
            output={"quality": current_quality},
            required_quality=required_quality,
        )

        # 3. Smart Escalation Loop if Quality Gate fails
        while eval_res["action"] == "ESCALATE":
            next_model = select_escalation_model(current_model)

            if not next_model:
                # Max tier reached and still failing
                node_status = "FAILED"
                break

            # Calculate additional penalties incurred from retrying with upgraded model
            deltas = calculate_escalation_deltas(
                from_model=current_model,
                to_model=next_model,
                base_metrics={"predicted_carbon": pred_carb, "predicted_cost": pred_cost, "predicted_latency": pred_lat},
            )

            # Accumulate extra carbon, cost, latency onto actual metrics
            act_carb += deltas["additional_carbon"]
            act_cost += deltas["additional_cost"]
            act_lat += deltas["additional_latency"]

            esc_record = {
                "node_id": node_id,
                "from_model": current_model,
                "to_model": next_model,
                "reason": f"Quality score {eval_res['quality_score']:.2f} below required {required_quality:.2f}",
                "additional_carbon": deltas["additional_carbon"],
                "additional_cost": deltas["additional_cost"],
                "additional_latency": deltas["additional_latency"],
            }

            node_escalations.append(esc_record)
            all_escalations.append(esc_record)

            # Upgrade model state
            current_model = next_model
            node_status = "ESCALATED"

            # Upgraded model quality score (upgraded model yields higher quality that satisfies threshold)
            upgraded_prof = MODEL_PROFILES.get(current_model, MODEL_PROFILES["AdvancedModel"])
            current_quality = upgraded_prof["quality"] + (qual_jitter if rng else 0.0)

            # Re-evaluate Quality Gate
            eval_res = evaluate_quality(
                node={"node_id": node_id, "model": current_model},
                output={"quality": current_quality},
                required_quality=required_quality,
            )

        # Determine start and finish times considering dependencies (DAG execution)
        pred_start = max([predicted_finish_times[dep] for dep in dependencies if dep in predicted_finish_times], default=0.0)
        predicted_finish_times[node_id] = pred_start + pred_lat

        act_start = max([actual_finish_times[dep] for dep in dependencies if dep in actual_finish_times], default=0.0)
        actual_finish_times[node_id] = act_start + act_lat

        total_act_carbon += act_carb
        total_act_cost += act_cost
        quality_scores.append(current_quality)

        node_result = {
            "node_id": node_id,
            "model": current_model,
            "original_model": model_name,
            "region": region_name,
            "predicted_latency": round(pred_lat, 2),
            "actual_latency": round(act_lat, 2),
            "predicted_carbon": round(pred_carb, 2),
            "actual_carbon": round(act_carb, 2),
            "predicted_cost": round(pred_cost, 4),
            "actual_cost": round(act_cost, 4),
            "quality": round(current_quality, 4),
            "required_quality": round(required_quality, 4),
            "status": node_status,
            "escalations": node_escalations,
        }
        node_results.append(node_result)

    # 4. Calculate total DAG latency (critical path duration)
    total_pred_latency = max(predicted_finish_times.values(), default=0.0)
    total_act_latency = max(actual_finish_times.values(), default=0.0)

    avg_final_quality = (sum(quality_scores) / len(quality_scores)) if quality_scores else 0.0
    overall_status = "failed" if any(n["status"] == "FAILED" for n in node_results) else "completed"

    return {
        "status": overall_status,
        "node_results": node_results,
        "total_predicted_carbon": round(total_pred_carbon, 2),
        "total_actual_carbon": round(total_act_carbon, 2),
        "total_predicted_cost": round(total_pred_cost, 4),
        "total_actual_cost": round(total_act_cost, 4),
        "total_predicted_latency": round(total_pred_latency, 2),
        "total_actual_latency": round(total_act_latency, 2),
        "final_quality": round(avg_final_quality, 4),
        "escalation_count": len(all_escalations),
        "escalations": all_escalations,
    }

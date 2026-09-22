"""
Execution Simulator Module for CarbonPilot.
"""

import random
from typing import Any, Dict, List, Optional, Union
from backend.engine.quality import evaluate_quality, select_escalation_model

MODEL_PROFILES: Dict[str, Dict[str, Any]] = {
    "EfficientModel": {
        "cost": 0.002,
        "carbon": 10.0,
        "latency": 2.0,
        "quality_base": 0.85,
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

REGION_PROFILES: Dict[str, Dict[str, float]] = {
    "Region-A": {
        "carbon_mult": 1.45,
        "latency_mult": 0.85,
    },
    "Region-B": {
        "carbon_mult": 0.52,
        "latency_mult": 1.0,
    },
    "Region-C": {
        "carbon_mult": 0.90,
        "latency_mult": 0.9,
    },
}


from backend.engine.carbon import load_model_profiles, load_region_profiles


def _get_model_metrics(model_name: str) -> Dict[str, Any]:
    try:
        profiles = load_model_profiles()
        for key, p in profiles.items():
            if key.lower() in model_name.lower() or model_name.lower() in key.lower():
                return {
                    "cost": round(p.get("cost_per_1k_tokens_usd", 0.0025) * 4.0, 4),
                    "carbon": round(p.get("carbon_factor", 1.0) * 25.0, 2),
                    "latency": round(p.get("base_latency_sec", 1.0) * 4.0, 2),
                    "quality_base": p.get("quality", 0.92),
                }
    except Exception:
        pass
    for key, metrics in MODEL_PROFILES.items():
        if key.lower() in model_name.lower() or model_name.lower() in key.lower():
            return metrics
    return MODEL_PROFILES["BalancedModel"]


def _get_region_metrics(region_name: str) -> Dict[str, float]:
    try:
        regions = load_region_profiles()
        for key, r in regions.items():
            if key.lower() in region_name.lower() or region_name.lower() in key.lower():
                return {
                    "carbon_mult": r.get("carbon_multiplier", 1.0),
                    "latency_mult": round(1.0 + r.get("network_latency_sec", 0.0), 2),
                }
    except Exception:
        pass
    for key, metrics in REGION_PROFILES.items():
        if key.lower() in region_name.lower() or region_name.lower() in key.lower():
            return metrics
    return {"carbon_mult": 1.0, "latency_mult": 1.0}


def execute_plan(
    plan: Union[Dict[str, Any], List[Dict[str, Any]]],
    seed: Optional[int] = None,
    forced_quality_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Simulates execution of a workflow execution plan."""
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
            nodes = [plan]

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

        pred_latency = float(node.get("predicted_latency", model_metrics["latency"] * region_metrics["latency_mult"]))
        pred_carbon = float(node.get("predicted_carbon", model_metrics["carbon"] * region_metrics["carbon_mult"]))
        pred_cost = float(node.get("predicted_cost", model_metrics["cost"]))

        var_lat = rng.uniform(0.95, 1.10)
        var_carb = rng.uniform(0.95, 1.08)
        var_cost = rng.uniform(0.98, 1.02)

        actual_latency = round(pred_latency * var_lat, 3)
        actual_carbon = round(pred_carbon * var_carb, 3)
        actual_cost = round(pred_cost * var_cost, 4)

        if node_id in forced_overrides:
            initial_quality = float(forced_overrides[node_id])
        elif "quality" in node or "quality_score" in node:
            initial_quality = float(node.get("quality_score", node.get("quality")))
        else:
            base_q = model_metrics["quality_base"]
            initial_quality = round(max(0.0, min(1.0, base_q + rng.uniform(-0.02, 0.03))), 4)

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

        while not eval_result["passed"]:
            next_model = select_escalation_model(current_model)
            if not next_model:
                break

            escalated = True
            num_escalations += 1
            next_model_name = str(next_model.get("name") if isinstance(next_model, dict) else next_model)

            escalated_model_metrics = _get_model_metrics(next_model_name)
            esc_pred_lat = escalated_model_metrics["latency"] * region_metrics["latency_mult"]
            esc_pred_carb = escalated_model_metrics["carbon"] * region_metrics["carbon_mult"]
            esc_pred_cost = escalated_model_metrics["cost"]

            add_lat = round(esc_pred_lat * rng.uniform(0.95, 1.08), 3)
            add_carb = round(esc_pred_carb * rng.uniform(0.95, 1.05), 3)
            add_cost = round(esc_pred_cost * rng.uniform(0.98, 1.02), 4)

            additional_latency += add_lat
            additional_carbon += add_carb
            additional_cost += add_cost

            actual_latency = round(actual_latency + add_lat, 3)
            actual_carbon = round(actual_carbon + add_carb, 3)
            actual_cost = round(actual_cost + add_cost, 4)

            current_model = next_model_name

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

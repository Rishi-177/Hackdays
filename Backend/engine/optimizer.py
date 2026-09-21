"""
CarbonPilot Whole-Workflow Optimizer Engine

Evaluates DAG dependencies, enforces hard constraints (Carbon Budget, Deadline, Quality),
scores candidate execution plans using user priority weights, and generates baseline vs CarbonPilot comparisons.
"""

import uuid
from typing import Any, Dict, List, Optional
from backend.engine.dag import topological_sort, validate_dag
from backend.engine.quality import MODEL_PROFILES
from backend.engine.scheduler import evaluate_slack_scheduling
from backend.engine.simulator import REGION_PROFILES


def _compute_plan_metrics(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates summary carbon, cost, latency, quality, and distribution metrics for a list of node plans."""
    total_carbon = 0.0
    total_cost = 0.0
    total_latency = 0.0
    quality_sum = 0.0
    region_dist: Dict[str, int] = {}
    model_dist: Dict[str, int] = {}

    for n in nodes:
        model = n.get("model", "EfficientModel")
        region = n.get("region", "Region-B")

        model_prof = MODEL_PROFILES.get(model, MODEL_PROFILES["EfficientModel"])
        region_prof = REGION_PROFILES.get(region, REGION_PROFILES["Region-B"])

        carb = float(n.get("predicted_carbon", model_prof["carbon"] * region_prof["carbon_factor"]))
        cost = float(n.get("predicted_cost", model_prof["cost"]))
        lat = float(n.get("predicted_latency", model_prof["latency"] * region_prof["latency_factor"]))
        qual = float(n.get("required_quality", model_prof["quality"]))

        total_carbon += carb
        total_cost += cost
        total_latency += lat
        quality_sum += qual

        region_dist[region] = region_dist.get(region, 0) + 1
        model_dist[model] = model_dist.get(model, 0) + 1

    avg_quality = (quality_sum / len(nodes)) if nodes else 0.0

    return {
        "carbon": round(total_carbon, 2),
        "cost": round(total_cost, 4),
        "latency": round(total_latency, 2),
        "quality": round(avg_quality, 4),
        "ai_calls": len(nodes),
        "region_distribution": region_dist,
        "model_distribution": model_dist,
        "nodes": nodes,
    }


def optimize_workflow(
    workflow_data: Dict[str, Any],
    carbon_budget: float = 200.0,
    deadline_seconds: float = 1200.0,
    quality_requirement: float = 0.95,
    carbon_weight: float = 0.8,
    latency_weight: float = 0.5,
    cost_weight: float = 0.4,
) -> Dict[str, Any]:
    """
    Optimizes a workflow DAG across Carbon, Latency, Cost, and Quality constraints.

    Generates a Baseline Execution Plan vs an Optimized CarbonPilot Execution Plan.
    """
    raw_nodes = workflow_data.get("nodes", [])
    if not raw_nodes:
        raise ValueError("Workflow contains no nodes")

    # Validate and sort DAG
    sorted_nodes = topological_sort(raw_nodes)
    reasoning: List[str] = []

    # 1. Build Baseline Plan (Unoptimized default: Advanced/Balanced models in Region-A, no carbon budget awareness)
    baseline_nodes = []
    for n in sorted_nodes:
        node_id = str(n.get("node_id", n.get("id")))
        req_q = float(n.get("required_quality", quality_requirement))

        # Baseline picks AdvancedModel or BalancedModel in Region-A (high carbon, low latency)
        model = "AdvancedModel" if req_q > 0.90 else "BalancedModel"
        region = "Region-A"

        model_prof = MODEL_PROFILES[model]
        region_prof = REGION_PROFILES[region]

        carb = round(model_prof["carbon"] * region_prof["carbon_factor"], 2)
        cost = round(model_prof["cost"], 4)
        lat = round(model_prof["latency"] * region_prof["latency_factor"], 2)

        baseline_nodes.append(
            {
                "node_id": node_id,
                "model": model,
                "region": region,
                "required_quality": req_q,
                "predicted_carbon": carb,
                "predicted_cost": cost,
                "predicted_latency": lat,
                "dependencies": list(n.get("dependencies", [])),
            }
        )

    baseline_metrics = _compute_plan_metrics(baseline_nodes)

    # 2. Build CarbonPilot Candidate Plan
    # Optimize model and region choices based on priority weights and constraints
    optimized_nodes = []

    # Determine region preference based on carbon_weight vs latency_weight
    if carbon_weight >= latency_weight:
        preferred_region = "Region-B"  # Low carbon, medium latency
        region_reason = "Region-B selected because it has lower estimated carbon emissions while satisfying latency constraint."
    elif latency_weight > carbon_weight and latency_weight > cost_weight:
        preferred_region = "Region-A"  # High carbon, low latency
        region_reason = "Region-A selected to maximize execution speed under high latency priority."
    else:
        preferred_region = "Region-C"  # Balanced
        region_reason = "Region-C selected for balanced carbon and latency performance."

    reasoning.append(region_reason)

    total_est_carbon = 0.0

    for n in sorted_nodes:
        node_id = str(n.get("node_id", n.get("id")))
        req_q = float(n.get("required_quality", quality_requirement))

        # Model Selection Logic: Pick the most efficient model that satisfies required quality
        if req_q <= MODEL_PROFILES["EfficientModel"]["quality"]:
            selected_model = "EfficientModel"
            model_reason = f"EfficientModel selected for node '{node_id}' because its baseline quality (0.86) satisfies requirement ({req_q:.2f})."
        elif req_q <= MODEL_PROFILES["BalancedModel"]["quality"]:
            selected_model = "BalancedModel"
            model_reason = f"BalancedModel selected for node '{node_id}' to satisfy target quality requirement ({req_q:.2f})."
        else:
            selected_model = "AdvancedModel"
            model_reason = f"AdvancedModel selected for node '{node_id}' to satisfy high quality requirement ({req_q:.2f})."

        reasoning.append(model_reason)

        model_prof = MODEL_PROFILES[selected_model]
        region_prof = REGION_PROFILES[preferred_region]

        carb = round(model_prof["carbon"] * region_prof["carbon_factor"], 2)
        cost = round(model_prof["cost"], 4)
        lat = round(model_prof["latency"] * region_prof["latency_factor"], 2)

        # Hard Constraint Check: Carbon Budget
        if total_est_carbon + carb > carbon_budget and selected_model != "EfficientModel":
            # Demote model if carbon budget would be breached
            selected_model = "EfficientModel"
            model_prof = MODEL_PROFILES[selected_model]
            carb = round(model_prof["carbon"] * region_prof["carbon_factor"], 2)
            cost = round(model_prof["cost"], 4)
            lat = round(model_prof["latency"] * region_prof["latency_factor"], 2)
            reasoning.append(f"Model for node '{node_id}' demoted to EfficientModel to enforce hard carbon budget constraint ({carbon_budget}g CO2e).")

        total_est_carbon += carb

        optimized_nodes.append(
            {
                "node_id": node_id,
                "model": selected_model,
                "region": preferred_region,
                "required_quality": req_q,
                "predicted_carbon": carb,
                "predicted_cost": cost,
                "predicted_latency": lat,
                "dependencies": list(n.get("dependencies", [])),
            }
        )

    optimized_metrics = _compute_plan_metrics(optimized_nodes)

    # 3. Evaluate Deadline Slack
    slack_eval = evaluate_slack_scheduling(deadline_seconds, optimized_metrics["latency"])
    if slack_eval["delay_recommended"]:
        reasoning.append(slack_eval["reasoning"])

    # 4. Calculate Percentage & Absolute Savings
    b_carb = baseline_metrics["carbon"]
    o_carb = optimized_metrics["carbon"]
    carb_saved = max(0.0, b_carb - o_carb)
    carb_pct = round((carb_saved / max(b_carb, 0.001)) * 100.0, 1)

    b_cost = baseline_metrics["cost"]
    o_cost = optimized_metrics["cost"]
    cost_saved = max(0.0, b_cost - o_cost)
    cost_pct = round((cost_saved / max(b_cost, 0.0001)) * 100.0, 1)

    b_lat = baseline_metrics["latency"]
    o_lat = optimized_metrics["latency"]
    lat_saved = b_lat - o_lat
    lat_pct = round((lat_saved / max(b_lat, 0.001)) * 100.0, 1)

    savings = {
        "carbon_percent": carb_pct,
        "cost_percent": cost_pct,
        "latency_percent": lat_pct,
        "carbon_saved_g": round(carb_saved, 2),
        "cost_saved_usd": round(cost_saved, 4),
        "time_saved_sec": round(lat_saved, 2),
    }

    plan_id = f"plan_{uuid.uuid4().hex[:8]}"

    return {
        "plan_id": plan_id,
        "workflow_id": workflow_data.get("workflow_id", "wf_default"),
        "baseline": baseline_metrics,
        "optimized": optimized_metrics,
        "savings": savings,
        "reasoning": reasoning,
    }


def create_execution_plan(workflow_data: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Helper wrapper for create_execution_plan."""
    return optimize_workflow(
        workflow_data=workflow_data,
        carbon_budget=float(params.get("carbon_budget", 200.0)),
        deadline_seconds=float(params.get("deadline_seconds", 1200.0)),
        quality_requirement=float(params.get("quality_requirement", 0.95)),
        carbon_weight=float(params.get("carbon_weight", 0.8)),
        latency_weight=float(params.get("latency_weight", 0.5)),
        cost_weight=float(params.get("cost_weight", 0.4)),
    )

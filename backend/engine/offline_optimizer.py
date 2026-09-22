"""
Offline-Aware Workflow Optimizer for CarbonPilot (Donut Challenge).

Performs multi-model optimization with graceful offline degradation.
When offline, only edge/small models are available, simulating local execution
with minimal carbon footprint and latency, while signaling when cloud model
escalation is needed upon reconnection.
"""

from typing import Dict, Any, List

# Model options with carbon (kg CO2e or g CO2e), latency (s), quality (0-1), and cost ($)
MODEL_OPTIONS: Dict[str, Dict[str, float]] = {
    "small": {"carbon": 0.007, "latency": 2.0, "quality": 0.92, "cost": 0.001},
    "efficient": {"carbon": 0.015, "latency": 4.0, "quality": 0.94, "cost": 0.003},
    "large": {"carbon": 0.041, "latency": 8.0, "quality": 0.97, "cost": 0.010},
}


def optimize_workflow(payload: Dict[str, Any], is_offline: bool = False) -> Dict[str, Any]:
    """
    Optimizes a workflow payload.
    Degrades gracefully when offline: only 'small' / local edge models are available.
    When online, selects among small, efficient, and large models according to constraints.
    """
    constraints = payload.get("constraints", {})
    carbon_budget = float(constraints.get("carbon_budget", payload.get("carbon_budget", 120.0)))
    quality_target = float(constraints.get("quality_target", payload.get("quality_requirement", 0.95)))
    deadline = float(constraints.get("deadline", payload.get("deadline_seconds", 60.0)))

    # Offline degradation: only small/local edge models available
    if is_offline:
        available_models = ["small"]
    else:
        available_models = ["small", "efficient", "large"]

    # Extract nodes from either Donut Challenge format ("nodes") or CarbonPilot DAG format ("dag.nodes")
    nodes: List[Dict[str, Any]] = []
    if "nodes" in payload and isinstance(payload["nodes"], list):
        nodes = payload["nodes"]
    elif "dag" in payload and isinstance(payload["dag"], dict) and "nodes" in payload["dag"]:
        nodes = payload["dag"]["nodes"]
    elif "workflow" in payload and isinstance(payload["workflow"], dict) and "nodes" in payload["workflow"]:
        nodes = payload["workflow"]["nodes"]

    # Fallback to single demo node if empty
    if not nodes:
        nodes = [{"id": "task_1", "name": "Primary Task"}]

    plan: List[Dict[str, Any]] = []
    total_carbon = 0.0
    total_latency = 0.0
    total_cost = 0.0

    for node in nodes:
        node_id = node.get("id") or node.get("node_id", f"node_{len(plan)+1}")
        node_name = node.get("name", node_id)
        required_quality = float(node.get("required_quality", quality_target))

        best_model = None
        best_score = float("inf")

        for model_name in available_models:
            model = MODEL_OPTIONS[model_name]
            # Respect carbon budget per node if specified
            if model["carbon"] > carbon_budget:
                continue
            # Balanced score: carbon prioritized + latency + cost
            score = model["carbon"] + (model["latency"] * 0.1) + (model["cost"] * 10.0)
            if score < best_score:
                best_score = score
                best_model = model_name

        if best_model is None:
            best_model = "small"  # Guaranteed fallback

        model_stats = MODEL_OPTIONS[best_model]
        plan.append({
            "node_id": node_id,
            "name": node_name,
            "model": best_model,
            "estimated_quality": model_stats["quality"],
            "carbon": model_stats["carbon"],
            "latency": model_stats["latency"],
            "cost": model_stats["cost"],
            "offline_mode": is_offline,
        })
        total_carbon += model_stats["carbon"]
        total_latency += model_stats["latency"]
        total_cost += model_stats["cost"]

    # Quality gate assessment
    final_quality = min(p["estimated_quality"] for p in plan) if plan else 0.0
    escalation_needed = final_quality < quality_target

    reasoning = []
    if is_offline:
        reasoning.append("Running in OFFLINE mode: restricted to local edge models ('small').")
        if escalation_needed:
            reasoning.append(
                f"Notice: Offline quality ({final_quality:.2f}) is below target ({quality_target:.2f}). "
                "Cloud model escalation will be performed once connectivity is restored."
            )
        else:
            reasoning.append(f"Offline execution satisfies quality target ({final_quality:.2f} >= {quality_target:.2f}).")
    else:
        reasoning.append("Running in ONLINE mode: full multi-model spectrum evaluated.")
        reasoning.append(f"Selected plan achieves quality={final_quality:.2f} within carbon_budget={carbon_budget}.")

    return {
        "plan": plan,
        "metrics": {
            "carbon": round(total_carbon, 4),
            "latency": round(total_latency, 2),
            "cost": round(total_cost, 4),
            "quality": round(final_quality, 3),
            "deadline_slack": round(deadline - total_latency, 2),
        },
        "escalation_needed": escalation_needed,
        "is_offline": is_offline,
        "reasoning": reasoning,
    }

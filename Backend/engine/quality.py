"""
CarbonPilot Quality Gate & Smart Escalation Engine

Provides quality evaluation functions and escalation model selection for AI workflow nodes.
"""

from typing import Any, Dict, List, Optional

# Standard model profiles for simulation
MODEL_PROFILES: Dict[str, Dict[str, float]] = {
    "EfficientModel": {
        "cost": 0.002,
        "carbon": 10.0,
        "latency": 1.5,
        "quality": 0.86,
    },
    "BalancedModel": {
        "cost": 0.005,
        "carbon": 22.0,
        "latency": 2.5,
        "quality": 0.93,
    },
    "AdvancedModel": {
        "cost": 0.012,
        "carbon": 45.0,
        "latency": 4.0,
        "quality": 0.98,
    },
}

# Standard escalation hierarchy
MODEL_HIERARCHY: List[str] = ["EfficientModel", "BalancedModel", "AdvancedModel"]


def evaluate_quality(
    node: Dict[str, Any],
    output: Any = None,
    required_quality: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluates whether the quality output of a node satisfies the required quality threshold.

    Args:
        node: Dictionary containing node metadata (e.g., node_id, model, required_quality).
        output: Simulated output or dictionary containing an explicit quality score.
        required_quality: Required threshold (0.0 to 1.0). Overrides node['required_quality'] if given.

    Returns:
        Dict formatted as:
        {
            "quality_score": 0.91,
            "required_quality": 0.90,
            "passed": True,
            "action": "PASS"  # or "ESCALATE"
        }
    """
    # 1. Determine required quality threshold
    if required_quality is None:
        required_quality = float(node.get("required_quality", 0.90))
    else:
        required_quality = float(required_quality)

    # 2. Extract quality score from output or node
    quality_score: Optional[float] = None

    if isinstance(output, dict):
        if "quality_score" in output:
            quality_score = float(output["quality_score"])
        elif "quality" in output:
            quality_score = float(output["quality"])

    if quality_score is None and isinstance(node, dict):
        if "quality_score" in node:
            quality_score = float(node["quality_score"])
        elif "quality" in node:
            quality_score = float(node["quality"])

    # Fallback to model profile baseline quality if not explicitly set
    if quality_score is None:
        model_name = node.get("model", "EfficientModel") if isinstance(node, dict) else "EfficientModel"
        profile = MODEL_PROFILES.get(model_name, MODEL_PROFILES["EfficientModel"])
        quality_score = float(profile["quality"])

    passed = quality_score >= required_quality
    action = "PASS" if passed else "ESCALATE"

    return {
        "quality_score": round(quality_score, 4),
        "required_quality": round(required_quality, 4),
        "passed": passed,
        "action": action,
    }


def select_escalation_model(
    current_model: str,
    available_models: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Selects the next stronger model tier in the escalation chain.

    Args:
        current_model: Name of the current model (e.g., 'EfficientModel').
        available_models: Optional custom list of models ordered by capability.

    Returns:
        Name of the next model in hierarchy, or None if already at highest tier.
    """
    hierarchy = available_models if available_models is not None else MODEL_HIERARCHY

    if current_model not in hierarchy:
        # If current model is unknown, default to first tier after EfficientModel or None
        return hierarchy[1] if len(hierarchy) > 1 else None

    current_idx = hierarchy.index(current_model)
    if current_idx + 1 < len(hierarchy):
        return hierarchy[current_idx + 1]

    return None


def calculate_escalation_deltas(
    from_model: str,
    to_model: str,
    base_metrics: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Calculates incremental carbon, cost, and latency incurred by escalating a node execution.

    Args:
        from_model: Original model name.
        to_model: Target upgraded model name.
        base_metrics: Optional dictionary with predicted node metrics.

    Returns:
        Dict with additional_carbon, additional_cost, and additional_latency.
    """
    from_profile = MODEL_PROFILES.get(from_model, MODEL_PROFILES["EfficientModel"])
    to_profile = MODEL_PROFILES.get(to_model, MODEL_PROFILES["AdvancedModel"])

    if base_metrics:
        # Scale proportionally to base metrics if provided
        carbon_factor = to_profile["carbon"] / max(from_profile["carbon"], 0.001)
        cost_factor = to_profile["cost"] / max(from_profile["cost"], 0.001)
        latency_factor = to_profile["latency"] / max(from_profile["latency"], 0.001)

        add_carbon = base_metrics.get("predicted_carbon", from_profile["carbon"]) * (carbon_factor - 1.0)
        add_cost = base_metrics.get("predicted_cost", from_profile["cost"]) * (cost_factor - 1.0)
        add_latency = base_metrics.get("predicted_latency", from_profile["latency"]) * (latency_factor - 1.0)
    else:
        # Absolute difference between model profiles
        add_carbon = max(0.0, to_profile["carbon"] - from_profile["carbon"])
        add_cost = max(0.0, to_profile["cost"] - from_profile["cost"])
        add_latency = max(0.0, to_profile["latency"] - from_profile["latency"])

    return {
        "additional_carbon": round(max(0.0, add_carbon), 4),
        "additional_cost": round(max(0.0, add_cost), 6),
        "additional_latency": round(max(0.0, add_latency), 4),
    }

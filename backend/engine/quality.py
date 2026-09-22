"""
Quality Evaluation & Model Escalation Module for CarbonPilot.
"""

import random
import hashlib
from typing import Any, Dict, List, Optional, Union

DEFAULT_MODEL_HIERARCHY = [
    "EfficientModel",
    "BalancedModel",
    "AdvancedModel"
]


def evaluate_quality(
    node: Union[Dict[str, Any], str],
    output: Any,
    required_quality: float,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """Evaluates the quality score of a node output against required quality threshold."""
    node_id = node.get("node_id", str(node)) if isinstance(node, dict) else str(node)
    quality_score: Optional[float] = None

    if isinstance(output, dict):
        if "quality_score" in output:
            quality_score = float(output["quality_score"])
        elif "quality" in output:
            quality_score = float(output["quality"])
    elif isinstance(output, (int, float)):
        quality_score = float(output)

    if quality_score is None and isinstance(node, dict):
        if "quality_score" in node:
            quality_score = float(node["quality_score"])
        elif "quality" in node:
            quality_score = float(node["quality"])

    if quality_score is None:
        model_name = node.get("model", "") if isinstance(node, dict) else ""
        if isinstance(model_name, dict):
            model_name = model_name.get("name", "")

        if "Advanced" in str(model_name):
            base_q = 0.96
        elif "Balanced" in str(model_name):
            base_q = 0.90
        elif "Efficient" in str(model_name):
            base_q = 0.84
        else:
            base_q = 0.88

        if seed is not None:
            rng = random.Random(seed + int(hashlib.md5(node_id.encode()).hexdigest(), 16) % 10000)
            variation = rng.uniform(-0.03, 0.03)
        else:
            hash_val = int(hashlib.md5(f"{node_id}:{output}".encode()).hexdigest(), 16)
            variation = ((hash_val % 100) / 1000.0) - 0.05

        quality_score = max(0.0, min(1.0, base_q + variation))

    passed = quality_score >= required_quality
    action = "PASS" if passed else "ESCALATE"

    return {
        "quality_score": round(quality_score, 4),
        "required_quality": round(required_quality, 4),
        "passed": passed,
        "action": action
    }


def select_escalation_model(
    current_model: Union[str, Dict[str, Any]],
    available_models: Optional[List[Union[str, Dict[str, Any]]]] = None
) -> Optional[Union[str, Dict[str, Any]]]:
    """Selects the next higher-performing model from available models hierarchy."""
    is_dict_input = isinstance(current_model, dict)
    current_name = current_model.get("name", "") if is_dict_input else str(current_model)

    if not available_models:
        available_models = DEFAULT_MODEL_HIERARCHY

    model_names = []
    for item in available_models:
        if isinstance(item, dict):
            model_names.append(item.get("name", ""))
        else:
            model_names.append(str(item))

    try:
        idx = model_names.index(current_name)
    except ValueError:
        idx = -1
        for i, name in enumerate(model_names):
            if name.lower() in current_name.lower() or current_name.lower() in name.lower():
                idx = i
                break

    if idx != -1 and idx < len(available_models) - 1:
        next_item = available_models[idx + 1]
        return next_item

    return None

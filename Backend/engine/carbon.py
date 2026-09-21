"""
CarbonPilot Carbon Intensity & Emission Calculator
"""

from typing import Dict
from backend.engine.quality import MODEL_PROFILES
from backend.engine.simulator import REGION_PROFILES


def calculate_node_carbon(model: str, region: str) -> float:
    """Calculates estimated carbon footprint for a node in g CO2e."""
    model_prof = MODEL_PROFILES.get(model, MODEL_PROFILES["EfficientModel"])
    region_prof = REGION_PROFILES.get(region, REGION_PROFILES["Region-B"])
    return round(model_prof["carbon"] * region_prof["carbon_factor"], 2)


def calculate_workflow_carbon(nodes: list) -> float:
    """Calculates total carbon across all nodes in a plan."""
    total = 0.0
    for n in nodes:
        model = n.get("model", "EfficientModel")
        region = n.get("region", "Region-B")
        if "predicted_carbon" in n:
            total += float(n["predicted_carbon"])
        else:
            total += calculate_node_carbon(model, region)
    return round(total, 2)

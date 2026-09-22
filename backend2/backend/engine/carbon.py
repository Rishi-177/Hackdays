"""
Carbon and Energy Estimation Module for CarbonPilot.
"""

from typing import Dict, Any

MODEL_CARBON_BASELINE: Dict[str, float] = {
    "EfficientModel": 10.0,   # g CO2e per invocation
    "BalancedModel": 25.0,
    "AdvancedModel": 60.0
}

REGION_CARBON_INTENSITY: Dict[str, float] = {
    "Region-A": 1.4,   # Coal heavy grid (g CO2e multiplier)
    "Region-B": 0.7,   # Hydro/Wind heavy grid (cleaner)
    "Region-C": 1.0    # Neutral grid
}

MODEL_LATENCY_BASELINE: Dict[str, float] = {
    "EfficientModel": 2.0,   # seconds
    "BalancedModel": 4.0,
    "AdvancedModel": 8.0
}

REGION_LATENCY_MULTIPLIER: Dict[str, float] = {
    "Region-A": 0.85,
    "Region-B": 1.0,
    "Region-C": 0.9
}

MODEL_COST_BASELINE: Dict[str, float] = {
    "EfficientModel": 0.002,   # USD per node
    "BalancedModel": 0.010,
    "AdvancedModel": 0.040
}


def estimate_node_metrics(model: str, region: str) -> Dict[str, float]:
    """Estimates carbon, cost, and latency for a node given model and region choices."""
    carbon_base = MODEL_CARBON_BASELINE.get(model, 25.0)
    region_mult = REGION_CARBON_INTENSITY.get(region, 1.0)
    estimated_carbon = round(carbon_base * region_mult, 2)

    latency_base = MODEL_LATENCY_BASELINE.get(model, 4.0)
    latency_mult = REGION_LATENCY_MULTIPLIER.get(region, 1.0)
    estimated_latency = round(latency_base * latency_mult, 2)

    estimated_cost = MODEL_COST_BASELINE.get(model, 0.010)

    return {
        "carbon": estimated_carbon,
        "latency": estimated_latency,
        "cost": estimated_cost
    }

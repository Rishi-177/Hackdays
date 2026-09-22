"""Carbon Accounting and Grid Simulation Module for CarbonPilot.

Calculates estimated carbon emissions, financial cost, and execution duration
for model-region combinations, and provides carbon budget and deadline slack validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

# Paths to simulation configuration datasets
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODELS_FILE = DATA_DIR / "models.json"
REGIONS_FILE = DATA_DIR / "regions.json"

_DEFAULT_MODELS = {
    "EfficientModel": {
        "id": "EfficientModel",
        "name": "CarbonPilot Efficient Model",
        "quality": 0.88,
        "base_latency_sec": 0.6,
        "latency_per_1k_tokens_sec": 0.65,
        "cost_per_1k_tokens_usd": 0.0008,
        "carbon_factor": 0.60,
    },
    "BalancedModel": {
        "id": "BalancedModel",
        "name": "CarbonPilot Balanced Model",
        "quality": 0.93,
        "base_latency_sec": 0.9,
        "latency_per_1k_tokens_sec": 1.10,
        "cost_per_1k_tokens_usd": 0.0025,
        "carbon_factor": 1.00,
    },
    "AdvancedModel": {
        "id": "AdvancedModel",
        "name": "CarbonPilot Advanced Model",
        "quality": 0.98,
        "base_latency_sec": 1.5,
        "latency_per_1k_tokens_sec": 2.00,
        "cost_per_1k_tokens_usd": 0.0090,
        "carbon_factor": 1.85,
    },
}

_DEFAULT_REGIONS = {
    "Region-A": {
        "id": "Region-A",
        "name": "US-East (High-Carbon Grid)",
        "carbon_multiplier": 1.45,
        "network_latency_sec": 0.05,
        "green_window": None,
    },
    "Region-B": {
        "id": "Region-B",
        "name": "EU-North (Low-Carbon Hydro Grid)",
        "carbon_multiplier": 0.52,
        "network_latency_sec": 0.28,
        "green_window": {
            "wait_seconds": 300,
            "cleaner_carbon_multiplier": 0.35,
        },
    },
    "Region-C": {
        "id": "Region-C",
        "name": "US-West (Solar-Mix Grid)",
        "carbon_multiplier": 0.90,
        "network_latency_sec": 0.12,
        "green_window": {
            "wait_seconds": 600,
            "cleaner_carbon_multiplier": 0.65,
        },
    },
}

# Dev 2 direct lookup metrics
MODEL_CARBON_BASELINE: Dict[str, float] = {
    "EfficientModel": 10.0,
    "BalancedModel": 25.0,
    "AdvancedModel": 60.0
}

REGION_CARBON_INTENSITY: Dict[str, float] = {
    "Region-A": 1.45,
    "Region-B": 0.52,
    "Region-C": 0.90
}


def load_model_profiles() -> Dict[str, Any]:
    """Loads simulated model profiles from JSON or fallback defaults."""
    if MODELS_FILE.exists():
        try:
            with open(MODELS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("models", _DEFAULT_MODELS)
        except Exception:
            pass
    return _DEFAULT_MODELS


def load_region_profiles() -> Dict[str, Any]:
    """Loads simulated regional grid profiles from JSON or fallback defaults."""
    if REGIONS_FILE.exists():
        try:
            with open(REGIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("regions", _DEFAULT_REGIONS)
        except Exception:
            pass
    return _DEFAULT_REGIONS


def estimate_node_metrics(model: str, region: str) -> Dict[str, float]:
    """Estimates carbon, cost, and latency for a node given model and region choices."""
    models = load_model_profiles()
    regions = load_region_profiles()

    model_info = models.get(model, models.get("BalancedModel", {}))
    region_info = regions.get(region, regions.get("Region-C", {}))

    carbon_base = MODEL_CARBON_BASELINE.get(model, 25.0)
    region_mult = region_info.get("carbon_multiplier", 1.0)
    estimated_carbon = round(carbon_base * region_mult, 2)

    latency_base = model_info.get("base_latency_sec", 1.0) * 4.0
    net_lat = region_info.get("network_latency_sec", 0.1)
    estimated_latency = round(latency_base + net_lat, 2)

    estimated_cost = round(model_info.get("cost_per_1k_tokens_usd", 0.002) * 4.0, 4)

    return {
        "carbon": estimated_carbon,
        "latency": estimated_latency,
        "cost": estimated_cost
    }


def calculate_node_carbon(
    model_id: str,
    region_id: str,
    token_count: int,
    is_green_window: bool = False,
) -> float:
    """Estimates carbon footprint (in grams CO2e) for a node operation."""
    models = load_model_profiles()
    regions = load_region_profiles()

    model = models.get(model_id, models.get("BalancedModel", {}))
    region = regions.get(region_id, regions.get("Region-C", {}))

    carbon_mult = region.get("carbon_multiplier", 1.0)
    if is_green_window and region.get("green_window"):
        gw = region["green_window"]
        carbon_mult = gw.get("cleaner_carbon_multiplier", carbon_mult * 0.7)

    model_factor = model.get("carbon_factor", 1.0)
    token_emission = (token_count / 1000.0) * 0.20 * model_factor
    base_overhead = 0.04 * model_factor

    total_carbon = (base_overhead + token_emission) * carbon_mult
    return round(total_carbon, 3)


def calculate_node_latency(
    model_id: str,
    region_id: str,
    token_count: int,
) -> float:
    """Estimates execution latency (in seconds) for a single node."""
    models = load_model_profiles()
    regions = load_region_profiles()

    model = models.get(model_id, models.get("BalancedModel", {}))
    region = regions.get(region_id, regions.get("Region-C", {}))

    base_lat = model.get("base_latency_sec", 1.0)
    token_lat = (token_count / 1000.0) * model.get("latency_per_1k_tokens_sec", 1.0)
    net_lat = region.get("network_latency_sec", 0.1)

    return round(base_lat + token_lat + net_lat, 2)


def calculate_node_cost(model_id: str, token_count: int) -> float:
    """Estimates monetary cost (in USD) for a single node execution."""
    models = load_model_profiles()
    model = models.get(model_id, models.get("BalancedModel", {}))

    cost_per_1k = model.get("cost_per_1k_tokens_usd", 0.002)
    base_cost = 0.0004
    return round(base_cost + (token_count / 1000.0) * cost_per_1k, 4)


def calculate_total_carbon(plan: Union[Dict[str, Any], Any]) -> float:
    """Calculates the total carbon footprint (in grams CO2e) of an execution plan."""
    if isinstance(plan, dict) and "estimated_carbon" in plan:
        return float(plan["estimated_carbon"])

    node_assignments = (
        plan.get("node_assignments", {}) if isinstance(plan, dict) else {}
    )
    if not node_assignments and isinstance(plan, dict):
        node_assignments = plan

    total_carbon = 0.0
    for node_info in node_assignments.values():
        if isinstance(node_info, dict):
            total_carbon += float(node_info.get("carbon_g", 0.0))

    return round(total_carbon, 3)


def check_carbon_budget(
    plan: Union[Dict[str, Any], float],
    budget: Optional[float],
) -> Dict[str, Any]:
    """Evaluates whether an execution plan satisfies the hard carbon budget constraint."""
    if isinstance(plan, (int, float)):
        carbon = float(plan)
    else:
        carbon = calculate_total_carbon(plan)

    if budget is None:
        return {
            "budget": None,
            "estimated_carbon": carbon,
            "remaining": None,
            "within_budget": True,
        }

    remaining = round(budget - carbon, 2)
    within_budget = carbon <= budget

    return {
        "budget": budget,
        "estimated_carbon": carbon,
        "remaining": remaining,
        "within_budget": within_budget,
    }


def calculate_slack(deadline: Optional[float], estimated_execution_time: float) -> Optional[float]:
    """Calculates deadline slack in seconds."""
    if deadline is None:
        return None
    return round(deadline - estimated_execution_time, 2)

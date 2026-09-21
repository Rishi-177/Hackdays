"""CarbonPilot Execution Scheduler Demonstration Script.

Simulates the execution scheduler choosing optimal model, region, and timing
configurations under diverse carbon, latency, budget, and deadline constraints.
"""

import json
import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.engine.scheduler import create_execution_plan


def print_plan_summary(title: str, plan_result: dict):
    print("\n" + "=" * 75)
    print(f"  SCENARIO: {title}")
    print("=" * 75)
    sel = plan_result["selected_plan"]
    print(f"Plan Name:           {sel['name']} ({sel['strategy']})")
    print(f"Schedule Timing:     {sel['schedule_mode']} (Delay: {sel['execution_delay_sec']}s)")
    print(f"Estimated Carbon:    {plan_result['estimated_carbon']} g CO2e  [Budget Met: {plan_result['carbon_budget_met']}]")
    print(f"Estimated Latency:   {plan_result['estimated_latency']} s        [Deadline Met: {plan_result['deadline_met']}]")
    print(f"Estimated Cost:      ${plan_result['estimated_cost']} USD")
    print(f"Average Quality:     {plan_result['estimated_quality'] * 100:.1f}%")
    print("-" * 75)
    print("Node Assignments:")
    for nid, na in sel["node_assignments"].items():
        print(f"  * {na['node_name']:<30} -> Model: {na['model']:<15} | Region: {na['region']:<10} | Carbon: {na['carbon_g']:.3f}g")

    print("-" * 75)
    print("Explainability Log (For Judges):")
    for idx, reason in enumerate(plan_result["reasoning"], 1):
        print(f"  {idx}. {reason}")


def run_demo():
    # Market Research Report Workflow
    workflow = {
        "id": "market_report",
        "name": "Market Research Report",
        "nodes": [
            {
                "id": "search",
                "name": "Search Documents",
                "type": "retrieval",
                "dependencies": [],
                "estimated_tokens": 1500,
            },
            {
                "id": "summary",
                "name": "Summarize",
                "type": "llm",
                "dependencies": ["search"],
                "required_quality": 0.88,
                "estimated_tokens": 2000,
            },
            {
                "id": "analysis",
                "name": "Deep Competitor Analysis",
                "type": "llm",
                "dependencies": ["summary"],
                "required_quality": 0.95,
                "estimated_tokens": 3000,
            },
            {
                "id": "report",
                "name": "Generate Report",
                "type": "llm",
                "dependencies": ["analysis"],
                "required_quality": 0.90,
                "estimated_tokens": 2500,
            },
        ],
    }

    # Scenario 1: Carbon Priority + Generous Deadline (30 mins = 1800s)
    # CarbonPilot detects deadline slack and schedules execution during clean renewable window!
    scen1_res = create_execution_plan(
        workflow=workflow,
        carbon_budget=2.0,
        deadline_seconds=1800.0,
        carbon_weight=0.8,
        latency_weight=0.1,
        cost_weight=0.1,
    )
    print_plan_summary("High Carbon Priority + Large Deadline Slack (Delay into Green Window)", scen1_res)

    # Scenario 2: Latency Priority + Tight Deadline (15s)
    # CarbonPilot cannot afford green-window wait; must execute immediately in lowest-latency region!
    scen2_res = create_execution_plan(
        workflow=workflow,
        deadline_seconds=15.0,
        carbon_weight=0.1,
        latency_weight=0.8,
        cost_weight=0.1,
    )
    print_plan_summary("High Latency Priority + Tight Deadline (Immediate US-East Execution)", scen2_res)

    # Scenario 3: Hard Carbon Budget Rejection
    # Carbon budget is capped at 0.5g CO2e, which is too low for this heavy multi-step workflow.
    scen3_res = create_execution_plan(
        workflow=workflow,
        carbon_budget=0.5,
        deadline_seconds=60.0,
        carbon_weight=0.5,
        latency_weight=0.3,
        cost_weight=0.2,
    )
    print_plan_summary("Hard Carbon Budget Rejection (Constraint Enforcement)", scen3_res)


if __name__ == "__main__":
    run_demo()

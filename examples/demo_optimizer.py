"""CarbonPilot Whole-Workflow Optimizer Demonstration Script.

Simulates the Hackathon Market Research Report workflow, demonstrating:
- DAG topological analysis and parallel group detection
- Redundant node pruning
- Linear step fusion
- Baseline vs. CarbonPilot metrics comparison
- Plain-language decision explainability
"""

import json
import sys
from pathlib import Path

# Add project root directory to sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.engine.optimizer import optimize_workflow


def run_demo():
    print("=" * 70)
    print("      CARBONPILOT — WHOLE-WORKFLOW OPTIMIZER DEMONSTRATION")
    print("=" * 70)

    # 1. Define Market Research Report Workflow
    workflow_input = {
        "id": "market_research_v1",
        "name": "Market Research Report",
        "nodes": [
            {
                "id": "search_primary",
                "name": "Primary Document Search",
                "type": "retrieval",
                "dependencies": [],
                "estimated_tokens": 1200,
            },
            {
                "id": "search_duplicate",
                "name": "Primary Document Search",
                "type": "retrieval",
                "dependencies": [],
                "estimated_tokens": 1200,
            },
            {
                "id": "summarize",
                "name": "Extract & Summarize",
                "type": "llm",
                "dependencies": ["search_primary", "search_duplicate"],
                "required_quality": 0.90,
                "estimated_tokens": 2000,
            },
            {
                "id": "competitor_analysis",
                "name": "Competitor Landscape Analysis",
                "type": "llm",
                "dependencies": ["summarize"],
                "required_quality": 0.95,
                "estimated_tokens": 3000,
            },
            {
                "id": "market_trend_analysis",
                "name": "Market Trend Analysis",
                "type": "llm",
                "dependencies": ["summarize"],
                "required_quality": 0.92,
                "estimated_tokens": 2800,
            },
            {
                "id": "draft_report",
                "name": "Draft Executive Report",
                "type": "llm",
                "dependencies": ["competitor_analysis", "market_trend_analysis"],
                "required_quality": 0.90,
                "estimated_tokens": 2500,
            },
            {
                "id": "polish_report",
                "name": "Format & Polish Report",
                "type": "llm",
                "dependencies": ["draft_report"],
                "required_quality": 0.92,
                "estimated_tokens": 1500,
            },
        ],
    }

    # 2. Optimization Constraints (e.g. from What-If sliders)
    constraints = {
        "carbon_budget": 3.0,     # max 3.0 grams CO2e
        "deadline": 25.0,         # max 25 seconds
        "priority_mode": "carbon",
        "enable_fusion": True,
        "enable_pruning": True,
    }

    print("\n[1] Submitting Workflow to CarbonPilot Optimizer...")
    print(f"Workflow: '{workflow_input['name']}' ({len(workflow_input['nodes'])} nodes)")
    print(f"Constraints: Carbon Budget = {constraints['carbon_budget']}g CO2e, Deadline = {constraints['deadline']}s\n")

    # 3. Execute Whole-Workflow Optimization
    result = optimize_workflow(workflow_input, constraints)

    base_metrics = result["estimated_improvement"]["baseline_metrics"]
    opt_metrics = result["estimated_improvement"]["optimized_metrics"]
    improvement = result["estimated_improvement"]

    # 4. Print Comparative Dashboard
    print("[2] METRICS COMPARISON (BASELINE vs. CARBONPILOT):")
    print("-" * 70)
    print(f"{'METRIC':<28} | {'BASELINE':<18} | {'CARBONPILOT':<18}")
    print("-" * 70)
    print(f"{'Total Nodes':<28} | {result['baseline_node_count']:<18} | {result['optimized_node_count']:<18}")
    print(f"{'Total Tokens':<28} | {base_metrics['total_tokens']:<18} | {opt_metrics['total_tokens']:<18}")
    print(f"{'Latency (sec)':<28} | {base_metrics['sequential_latency_sec']}s (seq)         | {opt_metrics['critical_path_latency_sec']}s (parallel)   (-{improvement['latency_reduction_pct']}%)")
    print(f"{'Carbon Footprint (g CO2e)':<28} | {base_metrics['estimated_carbon_g_co2']}g              | {opt_metrics['estimated_carbon_g_co2']}g             (-{improvement['carbon_reduction_pct']}%)")
    print(f"{'Estimated Cost ($ USD)':<28} | ${base_metrics['estimated_cost_usd']}           | ${opt_metrics['estimated_cost_usd']}          (-{improvement['cost_reduction_pct']}%)")
    print(f"{'Average Quality':<28} | {base_metrics['average_quality'] * 100:.1f}%              | {opt_metrics['average_quality'] * 100:.1f}%")
    print("-" * 70)

    # 5. Graph Structural Transformations
    print("\n[3] STRUCTURAL GRAPH TRANSFORMATIONS:")
    print(f"- Parallel Groups Identified: {result['parallel_groups']}")
    print(f"- Redundant Nodes Pruned: {len(result['removed_nodes'])}")
    for removed in result["removed_nodes"]:
        print(f"   * {removed['name']} ({removed['node_id']}) -> {removed['reason']}")

    print(f"- Operations Fused: {len(result['combined_nodes'])}")
    for fused in result["combined_nodes"]:
        print(f"   * {fused['name']} (merged {fused['merged_nodes']}, saved {fused['token_savings']} tokens)")

    # 6. Human-Readable Decision Explanations
    print("\n[4] EXPLAINABILITY LOGS (For Judges & Dashboard):")
    for idx, exp in enumerate(result["explanations"], 1):
        print(f"  {idx}. {exp}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE: Clean interface ready for FastAPI integration.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()

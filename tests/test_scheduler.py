"""Unit tests for CarbonPilot Execution Scheduler and Carbon Accounting."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models.workflow import Workflow, WorkflowNode
from backend.engine.carbon import (
    calculate_node_carbon,
    calculate_node_cost,
    calculate_node_latency,
    calculate_slack,
    calculate_total_carbon,
    check_carbon_budget,
    load_model_profiles,
    load_region_profiles,
)
from backend.engine.scheduler import (
    create_execution_plan,
    generate_candidate_plans,
)


class TestCarbonAccounting(unittest.TestCase):
    """Tests for carbon calculation, budget checking, and slack computation."""

    def test_load_profiles(self):
        models = load_model_profiles()
        regions = load_region_profiles()
        self.assertIn("EfficientModel", models)
        self.assertIn("BalancedModel", models)
        self.assertIn("AdvancedModel", models)
        self.assertIn("Region-A", regions)
        self.assertIn("Region-B", regions)
        self.assertIn("Region-C", regions)

    def test_node_carbon_and_latency(self):
        carb_b = calculate_node_carbon("BalancedModel", "Region-B", 1000)
        carb_a = calculate_node_carbon("BalancedModel", "Region-A", 1000)
        self.assertLess(carb_b, carb_a)

        lat_a = calculate_node_latency("BalancedModel", "Region-A", 1000)
        lat_b = calculate_node_latency("BalancedModel", "Region-B", 1000)
        self.assertLess(lat_a, lat_b)

        carb_b_green = calculate_node_carbon("BalancedModel", "Region-B", 1000, is_green_window=True)
        self.assertLess(carb_b_green, carb_b)

    def test_check_carbon_budget(self):
        plan_carbon = 175.0
        res_valid = check_carbon_budget(plan_carbon, budget=200.0)
        self.assertTrue(res_valid["within_budget"])
        self.assertEqual(res_valid["remaining"], 25.0)

        res_exceeded = check_carbon_budget(plan_carbon, budget=150.0)
        self.assertFalse(res_exceeded["within_budget"])
        self.assertEqual(res_exceeded["remaining"], -25.0)

    def test_calculate_slack(self):
        slack = calculate_slack(deadline=1800.0, estimated_execution_time=600.0)
        self.assertEqual(slack, 1200.0)

        tight_slack = calculate_slack(deadline=12.0, estimated_execution_time=8.0)
        self.assertEqual(tight_slack, 4.0)


class TestExecutionScheduler(unittest.TestCase):
    """Tests for candidate generation, constraint enforcement, and plan scoring."""

    def setUp(self):
        self.workflow = Workflow(
            id="test_wf",
            name="Test Workflow",
            nodes=[
                WorkflowNode(id="step1", name="Step 1", type="retrieval", dependencies=[], estimated_tokens=1000),
                WorkflowNode(
                    id="step2",
                    name="Step 2",
                    type="llm",
                    dependencies=["step1"],
                    required_quality=0.90,
                    estimated_tokens=2000,
                ),
            ],
        )

    def test_candidate_generation(self):
        candidates = generate_candidate_plans(self.workflow, deadline_seconds=1000.0)
        self.assertGreaterEqual(len(candidates), 4)

    def test_hard_constraint_carbon_budget_rejection(self):
        plan_result = create_execution_plan(
            workflow=self.workflow,
            carbon_budget=0.1,
        )
        self.assertFalse(plan_result["carbon_budget_met"])

    def test_hard_constraint_deadline_rejection(self):
        plan_result = create_execution_plan(
            workflow=self.workflow,
            deadline_seconds=0.5,
        )
        self.assertFalse(plan_result["deadline_met"])

    def test_deadline_slack_scheduling_green_window(self):
        plan_result = create_execution_plan(
            workflow=self.workflow,
            deadline_seconds=1800.0,
            carbon_weight=0.9,
            latency_weight=0.05,
            cost_weight=0.05,
        )
        self.assertTrue(plan_result["deadline_met"])
        sel = plan_result["selected_plan"]
        self.assertIn("Region-B", [na["region"] for na in sel["node_assignments"].values()])

    def test_weight_sensitivity_speed_vs_carbon(self):
        fast_result = create_execution_plan(
            workflow=self.workflow,
            latency_weight=1.0,
            carbon_weight=0.0,
            cost_weight=0.0,
            deadline_seconds=50.0,
        )
        green_result = create_execution_plan(
            workflow=self.workflow,
            latency_weight=0.0,
            carbon_weight=1.0,
            cost_weight=0.0,
            deadline_seconds=50.0,
        )

        fast_plan = fast_result["selected_plan"]
        green_plan = green_result["selected_plan"]

        self.assertLessEqual(fast_plan["total_latency_sec"], green_plan["total_latency_sec"])
        self.assertLessEqual(green_plan["total_carbon_g"], fast_plan["total_carbon_g"])


if __name__ == "__main__":
    unittest.main()

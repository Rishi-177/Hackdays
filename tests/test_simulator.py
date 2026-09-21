"""
Unit tests for CarbonPilot Execution Simulator Engine.
"""

import unittest
from backend.engine.simulator import execute_plan


class TestExecutionSimulator(unittest.TestCase):

    def setUp(self):
        self.sample_plan = {
            "plan_id": "demo_market_research",
            "nodes": [
                {
                    "node_id": "retrieve",
                    "model": "EfficientModel",
                    "region": "Region-B",
                    "predicted_latency": 2.0,
                    "predicted_carbon": 10.0,
                    "predicted_cost": 0.002,
                    "required_quality": 0.85,
                    "dependencies": [],
                },
                {
                    "node_id": "summarize",
                    "model": "EfficientModel",
                    "region": "Region-B",
                    "predicted_latency": 3.0,
                    "predicted_carbon": 15.0,
                    "predicted_cost": 0.003,
                    "required_quality": 0.85,
                    "dependencies": ["retrieve"],
                },
                {
                    "node_id": "analysis",
                    "model": "EfficientModel",
                    "region": "Region-B",
                    "predicted_latency": 4.0,
                    "predicted_carbon": 20.0,
                    "predicted_cost": 0.005,
                    "required_quality": 0.90,
                    "dependencies": ["summarize"],
                },
                {
                    "node_id": "generate_report",
                    "model": "BalancedModel",
                    "region": "Region-C",
                    "predicted_latency": 2.5,
                    "predicted_carbon": 22.0,
                    "predicted_cost": 0.005,
                    "required_quality": 0.92,
                    "dependencies": ["analysis"],
                },
            ],
        }

    def test_execute_plan_structure(self):
        res = execute_plan(self.sample_plan, random_seed=42)

        self.assertEqual(res["status"], "completed")
        self.assertEqual(len(res["node_results"]), 4)
        self.assertIn("total_actual_carbon", res)
        self.assertIn("total_actual_cost", res)
        self.assertIn("total_actual_latency", res)
        self.assertIn("final_quality", res)
        self.assertIn("escalations", res)

    def test_execute_plan_deterministic_with_seed(self):
        res1 = execute_plan(self.sample_plan, random_seed=123)
        res2 = execute_plan(self.sample_plan, random_seed=123)

        self.assertEqual(res1["total_actual_carbon"], res2["total_actual_carbon"])
        self.assertEqual(res1["total_actual_cost"], res2["total_actual_cost"])
        self.assertEqual(res1["total_actual_latency"], res2["total_actual_latency"])

    def test_execute_plan_forced_quality_gate_escalation(self):
        res = execute_plan(
            self.sample_plan,
            random_seed=42,
            force_quality_fail_nodes=["analysis"],
        )

        analysis_node = next(n for n in res["node_results"] if n["node_id"] == "analysis")

        self.assertEqual(analysis_node["status"], "ESCALATED")
        self.assertEqual(analysis_node["original_model"], "EfficientModel")
        self.assertEqual(analysis_node["model"], "BalancedModel")
        self.assertGreater(len(analysis_node["escalations"]), 0)
        self.assertEqual(analysis_node["escalations"][0]["from_model"], "EfficientModel")
        self.assertEqual(analysis_node["escalations"][0]["to_model"], "BalancedModel")
        self.assertGreater(res["escalation_count"], 0)


if __name__ == "__main__":
    unittest.main()

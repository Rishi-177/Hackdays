"""
Unit tests for engine/simulator.py (Execution Simulator)
"""

import sys
import os
import unittest

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.simulator import execute_plan


class TestExecutionSimulator(unittest.TestCase):

    def setUp(self):
        self.sample_plan = {
            "required_quality": 0.85,
            "nodes": [
                {
                    "node_id": "retrieve",
                    "model": "EfficientModel",
                    "region": "Region-B",
                    "predicted_latency": 2.0,
                    "predicted_carbon": 10.0,
                    "predicted_cost": 0.002,
                    "required_quality": 0.80,
                    "quality_score": 0.88
                },
                {
                    "node_id": "summarize",
                    "model": "BalancedModel",
                    "region": "Region-A",
                    "predicted_latency": 4.0,
                    "predicted_carbon": 25.0,
                    "predicted_cost": 0.010,
                    "required_quality": 0.90,
                    "quality_score": 0.92
                }
            ]
        }

    def test_execute_plan_success_schema(self):
        res = execute_plan(self.sample_plan, seed=42)

        self.assertEqual(res["status"], "completed")
        self.assertIn("node_results", res)
        self.assertIn("total_actual_carbon", res)
        self.assertIn("total_actual_cost", res)
        self.assertIn("total_actual_latency", res)
        self.assertIn("final_quality", res)
        self.assertIn("escalations", res)

        self.assertEqual(len(res["node_results"]), 2)
        node0 = res["node_results"][0]
        self.assertEqual(node0["node_id"], "retrieve")
        self.assertEqual(node0["status"], "COMPLETED")
        self.assertFalse(node0["escalated"])

    def test_execute_plan_seed_determinism(self):
        res1 = execute_plan(self.sample_plan, seed=123)
        res2 = execute_plan(self.sample_plan, seed=123)

        self.assertEqual(res1["total_actual_carbon"], res2["total_actual_carbon"])
        self.assertEqual(res1["total_actual_cost"], res2["total_actual_cost"])
        self.assertEqual(res1["total_actual_latency"], res2["total_actual_latency"])
        self.assertEqual(res1["final_quality"], res2["final_quality"])

    def test_execute_plan_forced_escalation(self):
        # Force retrieve node to fail quality check (score 0.70 < required 0.85)
        forced = {"retrieve": 0.70}
        res = execute_plan(self.sample_plan, seed=42, forced_quality_overrides=forced)

        self.assertGreater(len(res["escalations"]), 0)
        esc = res["escalations"][0]
        self.assertEqual(esc["node_id"], "retrieve")
        self.assertEqual(esc["original_model"], "EfficientModel")
        self.assertEqual(esc["final_model"], "BalancedModel")

        # Verify node_results reflects escalated model and status
        node0 = res["node_results"][0]
        self.assertEqual(node0["node_id"], "retrieve")
        self.assertEqual(node0["status"], "ESCALATED")
        self.assertTrue(node0["escalated"])
        self.assertEqual(node0["model"], "BalancedModel")
        self.assertGreater(node0["actual_carbon"], node0["predicted_carbon"])

    def test_execute_plan_list_input(self):
        nodes_list = self.sample_plan["nodes"]
        res = execute_plan(nodes_list, seed=42)
        self.assertEqual(res["status"], "completed")
        self.assertEqual(len(res["node_results"]), 2)


if __name__ == "__main__":
    unittest.main()

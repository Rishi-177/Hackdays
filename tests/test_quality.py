"""
Unit tests for CarbonPilot Quality Gate & Escalation Engine.
"""

import unittest
from backend.engine.quality import (
    evaluate_quality,
    select_escalation_model,
    calculate_escalation_deltas,
    MODEL_PROFILES,
    MODEL_HIERARCHY,
)


class TestQualityEngine(unittest.TestCase):

    def test_evaluate_quality_pass(self):
        node = {"node_id": "summarize", "model": "EfficientModel", "required_quality": 0.85}
        result = evaluate_quality(node=node, output={"quality_score": 0.92})

        self.assertTrue(result["passed"])
        self.assertEqual(result["action"], "PASS")
        self.assertEqual(result["quality_score"], 0.92)
        self.assertEqual(result["required_quality"], 0.85)

    def test_evaluate_quality_fail_escalate(self):
        node = {"node_id": "analysis", "model": "EfficientModel", "required_quality": 0.90}
        result = evaluate_quality(node=node, output={"quality_score": 0.86})

        self.assertFalse(result["passed"])
        self.assertEqual(result["action"], "ESCALATE")
        self.assertEqual(result["quality_score"], 0.86)
        self.assertEqual(result["required_quality"], 0.90)

    def test_evaluate_quality_fallback_to_model_baseline(self):
        node = {"node_id": "retrieve", "model": "AdvancedModel"}
        result = evaluate_quality(node=node, required_quality=0.95)

        self.assertTrue(result["passed"])
        self.assertEqual(result["action"], "PASS")
        self.assertEqual(result["quality_score"], MODEL_PROFILES["AdvancedModel"]["quality"])

    def test_select_escalation_model_chain(self):
        self.assertEqual(select_escalation_model("EfficientModel"), "BalancedModel")
        self.assertEqual(select_escalation_model("BalancedModel"), "AdvancedModel")
        self.assertIsNone(select_escalation_model("AdvancedModel"))

    def test_select_escalation_model_custom_hierarchy(self):
        custom = ["Tier1", "Tier2", "Tier3"]
        self.assertEqual(select_escalation_model("Tier1", available_models=custom), "Tier2")
        self.assertIsNone(select_escalation_model("Tier3", available_models=custom))

    def test_calculate_escalation_deltas(self):
        deltas = calculate_escalation_deltas("EfficientModel", "BalancedModel")
        self.assertGreater(deltas["additional_carbon"], 0)
        self.assertGreater(deltas["additional_cost"], 0)
        self.assertGreater(deltas["additional_latency"], 0)


if __name__ == "__main__":
    unittest.main()

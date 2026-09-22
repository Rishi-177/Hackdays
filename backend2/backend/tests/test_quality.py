"""
Unit tests for engine/quality.py (Quality Gate & Model Escalation)
"""

import sys
import os
import unittest

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.quality import evaluate_quality, select_escalation_model, DEFAULT_MODEL_HIERARCHY


class TestQualityGate(unittest.TestCase):

    def test_evaluate_quality_pass(self):
        node = {"node_id": "summarize", "model": "BalancedModel"}
        output = {"quality_score": 0.95, "result": "Good summary"}
        res = evaluate_quality(node, output, required_quality=0.90)

        self.assertEqual(res["quality_score"], 0.95)
        self.assertEqual(res["required_quality"], 0.90)
        self.assertTrue(res["passed"])
        self.assertEqual(res["action"], "PASS")

    def test_evaluate_quality_escalate(self):
        node = {"node_id": "analysis_a", "model": "EfficientModel"}
        output = {"quality_score": 0.82, "result": "Low quality analysis"}
        res = evaluate_quality(node, output, required_quality=0.90)

        self.assertEqual(res["quality_score"], 0.82)
        self.assertEqual(res["required_quality"], 0.90)
        self.assertFalse(res["passed"])
        self.assertEqual(res["action"], "ESCALATE")

    def test_evaluate_quality_numeric_output(self):
        node = {"node_id": "calc", "model": "EfficientModel"}
        res = evaluate_quality(node, output=0.88, required_quality=0.85)

        self.assertTrue(res["passed"])
        self.assertEqual(res["action"], "PASS")
        self.assertEqual(res["quality_score"], 0.88)

    def test_evaluate_quality_seed_determinism(self):
        node = {"node_id": "test_node", "model": "BalancedModel"}
        output = {"result": "No explicit quality score"}
        
        res1 = evaluate_quality(node, output, required_quality=0.90, seed=42)
        res2 = evaluate_quality(node, output, required_quality=0.90, seed=42)

        self.assertEqual(res1["quality_score"], res2["quality_score"])
        self.assertEqual(res1["action"], res2["action"])


class TestModelEscalation(unittest.TestCase):

    def test_select_escalation_model_string_hierarchy(self):
        self.assertEqual(select_escalation_model("EfficientModel"), "BalancedModel")
        self.assertEqual(select_escalation_model("BalancedModel"), "AdvancedModel")
        self.assertIsNone(select_escalation_model("AdvancedModel"))

    def test_select_escalation_model_dict_input(self):
        model_dict = {"name": "EfficientModel"}
        next_model = select_escalation_model(model_dict)
        self.assertEqual(next_model, "BalancedModel")

    def test_select_escalation_model_custom_hierarchy(self):
        custom_tier = ["NanoModel", "MicroModel", "MegaModel"]
        self.assertEqual(select_escalation_model("NanoModel", custom_tier), "MicroModel")
        self.assertEqual(select_escalation_model("MicroModel", custom_tier), "MegaModel")
        self.assertIsNone(select_escalation_model("MegaModel", custom_tier))

    def test_select_escalation_unknown_model(self):
        self.assertIsNone(select_escalation_model("UnknownModel"))


if __name__ == "__main__":
    unittest.main()

"""Unit tests for FastAPI Endpoints and Persistence (main.py & api/*)."""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app

client = TestClient(app)


class TestCarbonPilotAPI(unittest.TestCase):

    def test_health_check(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_get_demo_workflow(self):
        response = client.get("/api/workflows/demo")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "demo")
        self.assertIn("dag", data)
        self.assertGreater(len(data["dag"]["nodes"]), 0)

    def test_create_workflow(self):
        payload = {
            "name": "Custom Test Workflow",
            "description": "Test DAG",
            "dag": {
                "nodes": [
                    {"node_id": "step1", "name": "Step 1"},
                    {"node_id": "step2", "name": "Step 2"}
                ],
                "edges": [
                    {"source": "step1", "target": "step2"}
                ]
            }
        }
        response = client.post("/api/workflows", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["name"], "Custom Test Workflow")

        wf_id = data["id"]
        get_res = client.get(f"/api/workflows/{wf_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["name"], "Custom Test Workflow")

    def test_optimize_endpoint(self):
        payload = {
            "workflow_id": "demo",
            "carbon_budget": 200,
            "deadline_seconds": 1200,
            "quality_requirement": 0.95,
            "carbon_weight": 0.9,
            "latency_weight": 0.2,
            "cost_weight": 0.4
        }
        response = client.post("/api/optimize", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("plan_id", data)
        self.assertIn("baseline", data)
        self.assertIn("optimized", data)
        self.assertIn("savings", data)
        self.assertIn("reasoning", data)
        self.assertGreater(len(data["reasoning"]), 0)

    def test_execute_plan_endpoint(self):
        opt_res = client.post("/api/optimize", json={"workflow_id": "demo"})
        self.assertEqual(opt_res.status_code, 200)
        plan_id = opt_res.json()["plan_id"]

        exec_res = client.post(f"/api/execute/{plan_id}", json={"seed": 42})
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertEqual(exec_data["status"], "completed")
        self.assertIn("total_actual_carbon", exec_data)
        self.assertIn("node_results", exec_data)

    def test_quality_check_endpoint(self):
        payload = {
            "node": {"node_id": "analysis_a", "model": "BalancedModel"},
            "output": {"quality_score": 0.96},
            "required_quality": 0.90
        }
        response = client.post("/api/quality-check", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["passed"])
        self.assertEqual(data["action"], "PASS")

    def test_dashboard_endpoint(self):
        response = client.get("/api/dashboard/demo")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["workflow_id"], "demo")
        self.assertIn("baseline", data)
        self.assertIn("optimized", data)
        self.assertIn("savings", data)
        self.assertIn("nodes", data)
        self.assertIn("execution_history", data)


if __name__ == "__main__":
    unittest.main()

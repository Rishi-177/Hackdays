"""
End-to-End API Unit Tests for CarbonPilot FastAPI Layer
"""

import os
import unittest
from fastapi.testclient import TestClient

# Set temp file SQLite database for testing
TEST_DB_PATH = "test_carbonpilot.db"
os.environ["SQLITE_DB_PATH"] = TEST_DB_PATH

from backend.main import app
from backend.db.database import init_db


class TestCarbonPilotAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_workflow_crud_and_end_to_end_flow(self):
        # 1. Create Workflow
        wf_payload = {
            "name": "Market Research Report",
            "description": "AI-generated report from document corpus",
            "nodes": [
                {
                    "node_id": "retrieve",
                    "model": "EfficientModel",
                    "region": "Region-B",
                    "required_quality": 0.85,
                    "dependencies": [],
                },
                {
                    "node_id": "summarize",
                    "model": "EfficientModel",
                    "region": "Region-B",
                    "required_quality": 0.85,
                    "dependencies": ["retrieve"],
                },
                {
                    "node_id": "analysis",
                    "model": "EfficientModel",
                    "region": "Region-B",
                    "required_quality": 0.90,
                    "dependencies": ["summarize"],
                },
                {
                    "node_id": "generate_report",
                    "model": "BalancedModel",
                    "region": "Region-C",
                    "required_quality": 0.92,
                    "dependencies": ["analysis"],
                },
            ],
        }

        res_wf = self.client.post("/api/workflows", json=wf_payload)
        self.assertEqual(res_wf.status_code, 201)
        wf_data = res_wf.json()
        workflow_id = wf_data["workflow_id"]
        self.assertTrue(workflow_id.startswith("wf_"))

        # 2. Get Workflow by ID
        res_get_wf = self.client.get(f"/api/workflows/{workflow_id}")
        self.assertEqual(res_get_wf.status_code, 200)
        self.assertEqual(res_get_wf.json()["name"], "Market Research Report")

        # 3. List Workflows
        res_list = self.client.get("/api/workflows")
        self.assertEqual(res_list.status_code, 200)
        self.assertGreater(len(res_list.json()), 0)

        # 4. Optimize Plan (What-If Engine)
        opt_payload = {
            "workflow_id": workflow_id,
            "carbon_budget": 200.0,
            "deadline_seconds": 1200.0,
            "quality_requirement": 0.90,
            "carbon_weight": 0.8,
            "latency_weight": 0.5,
            "cost_weight": 0.4,
        }

        res_opt = self.client.post("/api/optimize", json=opt_payload)
        self.assertEqual(res_opt.status_code, 200)
        opt_data = res_opt.json()
        plan_id = opt_data["plan_id"]

        self.assertIn("baseline", opt_data)
        self.assertIn("optimized", opt_data)
        self.assertIn("savings", opt_data)
        self.assertIn("reasoning", opt_data)

        # 5. Execute Plan
        exec_payload = {
            "random_seed": 42,
            "force_quality_fail_nodes": ["analysis"],
        }

        res_exec = self.client.post(f"/api/execute/{plan_id}", json=exec_payload)
        self.assertEqual(res_exec.status_code, 200)
        exec_data = res_exec.json()

        self.assertEqual(exec_data["status"], "completed")
        self.assertGreater(exec_data["total_actual_carbon"], 0)
        self.assertIn("node_results", exec_data)

        # 6. Quality Check Endpoint
        qual_payload = {
            "node": {"node_id": "analysis", "model": "EfficientModel"},
            "output": {"quality": 0.88},
            "required_quality": 0.90,
        }

        res_qual = self.client.post("/api/quality-check", json=qual_payload)
        self.assertEqual(res_qual.status_code, 200)
        qual_data = res_qual.json()
        self.assertFalse(qual_data["passed"])
        self.assertEqual(qual_data["action"], "ESCALATE")

        # 7. Dashboard Endpoint
        res_dash = self.client.get(f"/api/dashboard/{workflow_id}")
        self.assertEqual(res_dash.status_code, 200)
        dash_data = res_dash.json()

        self.assertEqual(dash_data["workflow_id"], workflow_id)
        self.assertIn("baseline_metrics", dash_data)
        self.assertIn("carbonpilot_metrics", dash_data)
        self.assertIn("savings", dash_data)
        self.assertGreater(len(dash_data["execution_history"]), 0)


if __name__ == "__main__":
    unittest.main()

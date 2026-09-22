"""
Unit and Integration Tests for Donut Challenge (Intermittent Connectivity).
"""

import unittest
import uuid
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from backend.db.async_database import AsyncSessionLocal, init_async_db
from backend.db.queue_models import WorkflowQueue
from backend.engine.offline_optimizer import optimize_workflow, MODEL_OPTIONS
from backend.engine.sync_engine import process_pending_workflows


class TestDonutSyncSuite(unittest.TestCase):
    """Test suite covering offline queueing, idempotency, sync engine, and degradation."""

    @classmethod
    def setUpClass(cls):
        # Initialize async database tables
        asyncio.run(init_async_db())
        cls.client = TestClient(app)

    def test_health_check_endpoint(self):
        """Verify health check returns status ok and timestamp."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("timestamp", data)

    def test_offline_optimizer_online_selection(self):
        """Verify that in online mode the optimizer evaluates multiple models."""
        payload = {
            "constraints": {"carbon_budget": 0.05, "quality_target": 0.95, "deadline": 60},
            "nodes": [
                {"id": "node_1", "required_quality": 0.92},
                {"id": "node_2", "required_quality": 0.96},
            ]
        }
        res = optimize_workflow(payload, is_offline=False)
        self.assertFalse(res["is_offline"])
        self.assertEqual(len(res["plan"]), 2)
        self.assertIn("metrics", res)
        self.assertGreater(res["metrics"]["quality"], 0)

    def test_offline_optimizer_graceful_degradation(self):
        """Verify that in offline mode the optimizer only uses 'small' models and alerts on escalation."""
        payload = {
            "constraints": {"carbon_budget": 0.05, "quality_target": 0.95, "deadline": 60},
            "nodes": [
                {"id": "node_1", "required_quality": 0.95},
                {"id": "node_2", "required_quality": 0.96},
            ]
        }
        res = optimize_workflow(payload, is_offline=True)
        self.assertTrue(res["is_offline"])
        for node_plan in res["plan"]:
            self.assertEqual(node_plan["model"], "small")
            self.assertTrue(node_plan["offline_mode"])
        # Because small model quality is 0.92 and target is 0.95, escalation should be needed
        self.assertTrue(res["escalation_needed"])

    def test_queue_workflow_submission(self):
        """Verify submitting a workflow creates a queue item with idempotency tracking."""
        wf_id = f"test_queue_{uuid.uuid4().hex[:8]}"
        payload = {
            "workflow_id": wf_id,
            "is_offline": False,
            "constraints": {"carbon_budget": 0.05, "quality_target": 0.90, "deadline": 30},
            "nodes": [{"id": "step_a"}, {"id": "step_b"}]
        }
        res = self.client.post("/workflows", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["workflow_id"], wf_id)
        self.assertEqual(data["status"], "queued")
        self.assertFalse(data["is_offline"])

    def test_idempotency_duplicate_rejection(self):
        """Verify re-submitting the exact same workflow_id returns duplicate without creating extra items."""
        wf_id = f"test_idemp_{uuid.uuid4().hex[:8]}"
        payload = {
            "workflow_id": wf_id,
            "is_offline": True,
            "nodes": [{"id": "step_single"}]
        }
        # First submission
        res1 = self.client.post("/workflows", json=payload)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["status"], "queued")

        # Duplicate submission with identical key
        res2 = self.client.post("/workflows", json=payload)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["status"], "duplicate")
        self.assertEqual(data2["message"], "Already queued")

    def test_get_queued_workflow_status(self):
        """Verify querying workflow status by ID."""
        wf_id = f"test_get_{uuid.uuid4().hex[:8]}"
        payload = {"workflow_id": wf_id, "is_offline": False, "nodes": [{"id": "n1"}]}
        self.client.post("/workflows", json=payload)

        res = self.client.get(f"/workflows/{wf_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["workflow_id"], wf_id)
        self.assertIn("status", data)

        # 404 on missing workflow
        res_404 = self.client.get("/workflows/non_existent_workflow_xyz")
        self.assertEqual(res_404.status_code, 404)

    def test_sync_engine_execution(self):
        """Verify that process_pending_workflows transitions pending items to completed."""
        async def run_sync_test():
            wf_id = f"test_sync_proc_{uuid.uuid4().hex[:8]}"
            async with AsyncSessionLocal() as session:
                queue_item = WorkflowQueue(
                    workflow_id=wf_id,
                    payload={"nodes": [{"id": "n1"}, {"id": "n2"}]},
                    is_offline=True,
                    status="pending"
                )
                session.add(queue_item)
                await session.commit()

                # Run sync processing
                await process_pending_workflows(session)

                # Verify status updated to completed
                stmt = select(WorkflowQueue).where(WorkflowQueue.workflow_id == wf_id)
                res = await session.execute(stmt)
                updated = res.scalar_one()
                self.assertEqual(updated.status, "completed")
                self.assertIsNotNone(updated.payload.get("result"))
                self.assertTrue(updated.payload["result"]["is_offline"])

        asyncio.run(run_sync_test())

    def test_sync_engine_retry_and_backoff(self):
        """Verify retry count increments on failure and transitions to failed at limit."""
        async def run_retry_test():
            wf_id = f"test_retry_{uuid.uuid4().hex[:8]}"
            async with AsyncSessionLocal() as session:
                # Malformed payload to force an exception in optimizer
                bad_item = WorkflowQueue(
                    workflow_id=wf_id,
                    payload={"constraints": {"carbon_budget": "invalid_not_a_number"}},
                    is_offline=False,
                    status="pending",
                    retry_count=4  # 4th retry, next will reach 5 (max)
                )
                session.add(bad_item)
                await session.commit()

                await process_pending_workflows(session)

                stmt = select(WorkflowQueue).where(WorkflowQueue.workflow_id == wf_id)
                res = await session.execute(stmt)
                updated = res.scalar_one()
                self.assertEqual(updated.retry_count, 5)
                self.assertEqual(updated.status, "failed")
                self.assertIsNotNone(updated.error_message)

        asyncio.run(run_retry_test())

    def test_list_all_queued_workflows(self):
        """Verify GET /workflows lists tracked queue items."""
        res = self.client.get("/workflows")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_manual_sync_endpoint(self):
        """Verify POST /sync triggers background queue processing."""
        res = self.client.post("/sync")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("message"), "Sync triggered")
        self.assertIn("timestamp", data)


if __name__ == "__main__":
    unittest.main()

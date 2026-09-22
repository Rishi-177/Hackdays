"""
End-to-End Demonstration Script for Donut Challenge (Intermittent Connectivity).

Simulates the complete cycle:
1. Online Workflow Submission & Immediate Processing
2. Disconnect & Offline Queueing
3. Idempotency Key Duplicate Prevention
4. Reconnection & Background Sync with Graceful Edge Degradation
5. Fault Tolerance & Exponential Backoff Handling
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add project root directory to sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Use FastAPI TestClient for standalone execution without requiring live port binding
from fastapi.testclient import TestClient
from main import app
from backend.engine.offline_optimizer import optimize_workflow


def print_banner(title: str):
    width = 75
    print("\n" + "=" * width)
    print(f" [DONUT CHALLENGE] {title.upper()}")
    print("=" * width)


def print_step(step_num: int, title: str):
    print(f"\n[{step_num}] {title}")
    print("-" * 65)


def run_demo():
    print_banner("Donut Challenge: Intermittent Connectivity Demo")
    client = TestClient(app)

    # 1. Health Check
    print_step(1, "Verify System & Health Status")
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print(f"✅ Backend status : {health_data.get('status')}")
    print(f"✅ Server timestamp: {health_data.get('timestamp')}")

    # 2. Online Mode: Normal Operation
    print_step(2, "Online Mode: Submit Workflow Under Clean Connectivity")
    online_wf_id = f"demo_online_{int(time.time())}"
    online_payload = {
        "workflow_id": online_wf_id,
        "is_offline": False,
        "constraints": {
            "carbon_budget": 0.05,
            "quality_target": 0.95,
            "deadline": 60,
        },
        "nodes": [
            {"id": "ingest", "name": "Ingest Stream", "required_quality": 0.90},
            {"id": "parse", "name": "Token Parse", "required_quality": 0.92},
            {"id": "reason", "name": "Synthesis", "required_quality": 0.96},
        ],
    }

    res = client.post("/workflows", json=online_payload)
    print(f"Submission Response ({res.status_code}): {res.json()}")
    assert res.json().get("status") == "queued"

    # Allow background sync task to process
    time.sleep(0.5)
    res = client.get(f"/workflows/{online_wf_id}")
    wf_state = res.json()
    print(f"Status in Queue : {wf_state.get('status').upper()}")
    print(f"Assigned Models : {[p['model'] for p in wf_state.get('result', {}).get('plan', [])]}")
    print(f"Carbon Footprint: {wf_state.get('result', {}).get('metrics', {}).get('carbon')} kg CO2e")
    print(f"Quality Achieved: {wf_state.get('result', {}).get('metrics', {}).get('quality')}")

    # 3. Disconnect Simulation: Offline Queueing
    print_step(3, "Disconnect Simulation: Submitting Workflow While OFFLINE")
    offline_wf_id = f"demo_offline_{int(time.time())}"
    offline_payload = {
        "workflow_id": offline_wf_id,
        "is_offline": True,
        "constraints": {
            "carbon_budget": 0.02,
            "quality_target": 0.95,
            "deadline": 45,
        },
        "nodes": [
            {"id": "sensor_a", "name": "Telemetry Reading", "required_quality": 0.90},
            {"id": "filter", "name": "Anomaly Filter", "required_quality": 0.93},
            {"id": "alert", "name": "Emergency Escalation", "required_quality": 0.96},
        ],
    }

    res = client.post("/workflows", json=offline_payload)
    print(f"Offline Submission Response: {res.json()}")
    assert res.json().get("status") == "queued"
    assert res.json().get("is_offline") is True
    print("✅ Workflow safely enqueued with offline state flag.")

    # 4. Idempotency Key Verification (Duplicate Protection)
    print_step(4, "Idempotency Verification: Re-transmitting Duplicate Workflow ID")
    res_dup = client.post("/workflows", json=offline_payload)
    dup_data = res_dup.json()
    print(f"Duplicate Submission Response: {dup_data}")
    assert dup_data.get("status") == "duplicate", f"Expected duplicate status, got: {dup_data}"
    assert "Already queued" in dup_data.get("message", "")
    print(f"✅ Duplicate key successfully intercepted and discarded. Zero redundant side effects!")

    # 5. Reconnection & Background Sync
    print_step(5, "Reconnection & Background Sync Drain")
    print("Triggering background sync (/sync)...")
    res_sync = client.post("/sync")
    print(f"Sync Trigger Response: {res_sync.json()}")

    # Allow background sync task to process
    time.sleep(0.5)

    res = client.get(f"/workflows/{offline_wf_id}")
    processed_wf = res.json()
    print(f"\nFinal State for {offline_wf_id}:")
    print(f" - Status           : {processed_wf.get('status').upper()}")
    print(f" - Offline Flag     : {processed_wf.get('is_offline')}")
    print(f" - Retries Executed : {processed_wf.get('retry_count')}")

    result = processed_wf.get("result", {})
    plan = result.get("plan", [])
    metrics = result.get("metrics", {})

    print(f" - Graceful Degradation Models: {[p['model'] for p in plan]}")
    print(f" - Total Carbon (Edge-Optimized): {metrics.get('carbon')} kg CO2e")
    print(f" - Edge Latency                : {metrics.get('latency')}s")
    print(f" - Escalation Needed           : {result.get('escalation_needed')}")
    print(" - Reasonings:")
    for r in result.get("reasoning", []):
        print(f"    * {r}")

    # 6. Graceful Degradation Comparison Table
    print_step(6, "Architecture Summary & Degradation Matrix")
    online_eval = optimize_workflow(online_payload, is_offline=False)
    offline_eval = optimize_workflow(offline_payload, is_offline=True)

    print(f"{'Metric':<25} | {'Online Mode':<20} | {'Offline Mode (Degraded)':<25}")
    print("-" * 75)
    print(f"{'Available Models':<25} | {'small, efficient, large':<20} | {'small (edge-only)':<25}")
    print(f"{'Total Carbon':<25} | {str(online_eval['metrics']['carbon']) + ' kg CO2e':<20} | {str(offline_eval['metrics']['carbon']) + ' kg CO2e':<25}")
    print(f"{'Latency':<25} | {str(online_eval['metrics']['latency']) + 's':<20} | {str(offline_eval['metrics']['latency']) + 's':<25}")
    print(f"{'Escalation Flag':<25} | {str(online_eval['escalation_needed']):<20} | {str(offline_eval['escalation_needed']):<25}")

    print_banner("Donut Challenge Demonstration Completed Successfully!")


if __name__ == "__main__":
    run_demo()

"""
Repository CRUD Operations Module for CarbonPilot.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from backend.db.database import DB_FILE, DB_MODE, _IN_MEMORY_STORE, DEMO_WORKFLOW


def save_workflow(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    wf_id = workflow_data.get("id") or f"wf_{uuid.uuid4().hex[:8]}"
    created_at = workflow_data.get("created_at") or datetime.now(timezone.utc).isoformat()

    record = {
        "id": wf_id,
        "name": workflow_data.get("name", "Untitled Workflow"),
        "description": workflow_data.get("description", ""),
        "dag": workflow_data.get("dag", {}),
        "created_at": created_at
    }

    _IN_MEMORY_STORE["workflows"][wf_id] = record

    if DB_MODE != "memory":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO workflows (id, name, description, dag, created_at) VALUES (?, ?, ?, ?, ?)",
                (record["id"], record["name"], record["description"], json.dumps(record["dag"]), record["created_at"])
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Repository Warning] SQLite save_workflow error: {e}")

    return record


def get_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    if workflow_id == "demo":
        return _IN_MEMORY_STORE["workflows"].get("demo", DEMO_WORKFLOW)

    if workflow_id in _IN_MEMORY_STORE["workflows"]:
        return _IN_MEMORY_STORE["workflows"][workflow_id]

    if DB_MODE != "memory":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, dag, created_at FROM workflows WHERE id = ?", (workflow_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                record = {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "dag": json.loads(row[3]),
                    "created_at": row[4]
                }
                _IN_MEMORY_STORE["workflows"][workflow_id] = record
                return record
        except Exception as e:
            print(f"[Repository Warning] SQLite get_workflow error: {e}")

    return None


def save_execution_plan(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    plan_id = plan_data.get("id") or plan_data.get("plan_id") or f"plan_{uuid.uuid4().hex[:8]}"
    created_at = plan_data.get("created_at") or datetime.now(timezone.utc).isoformat()

    record = {
        "id": plan_id,
        "plan_id": plan_id,
        "workflow_id": plan_data.get("workflow_id", "demo"),
        "baseline": plan_data.get("baseline", {}),
        "optimized": plan_data.get("optimized", {}),
        "savings": plan_data.get("savings", {}),
        "reasoning": plan_data.get("reasoning", []),
        "created_at": created_at
    }

    _IN_MEMORY_STORE["execution_plans"][plan_id] = record

    if DB_MODE != "memory":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO execution_plans (id, workflow_id, baseline, optimized, savings, reasoning, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record["id"],
                    record["workflow_id"],
                    json.dumps(record["baseline"]),
                    json.dumps(record["optimized"]),
                    json.dumps(record["savings"]),
                    json.dumps(record["reasoning"]),
                    record["created_at"]
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Repository Warning] SQLite save_execution_plan error: {e}")

    return record


def get_execution_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    if plan_id in _IN_MEMORY_STORE["execution_plans"]:
        return _IN_MEMORY_STORE["execution_plans"][plan_id]

    if DB_MODE != "memory":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT id, workflow_id, baseline, optimized, savings, reasoning, created_at FROM execution_plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                record = {
                    "id": row[0],
                    "plan_id": row[0],
                    "workflow_id": row[1],
                    "baseline": json.loads(row[2]),
                    "optimized": json.loads(row[3]),
                    "savings": json.loads(row[4]),
                    "reasoning": json.loads(row[5]),
                    "created_at": row[6]
                }
                _IN_MEMORY_STORE["execution_plans"][plan_id] = record
                return record
        except Exception as e:
            print(f"[Repository Warning] SQLite get_execution_plan error: {e}")

    return None


def get_latest_execution_plan_by_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    plans = [p for p in _IN_MEMORY_STORE["execution_plans"].values() if p.get("workflow_id") == workflow_id]
    if plans:
        plans.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return plans[0]

    if DB_MODE != "memory":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, workflow_id, baseline, optimized, savings, reasoning, created_at FROM execution_plans WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1",
                (workflow_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                record = {
                    "id": row[0],
                    "plan_id": row[0],
                    "workflow_id": row[1],
                    "baseline": json.loads(row[2]),
                    "optimized": json.loads(row[3]),
                    "savings": json.loads(row[4]),
                    "reasoning": json.loads(row[5]),
                    "created_at": row[6]
                }
                return record
        except Exception as e:
            print(f"[Repository Warning] SQLite get_latest_execution_plan error: {e}")

    return None


def save_execution(execution_data: Dict[str, Any]) -> Dict[str, Any]:
    exec_id = execution_data.get("id") or execution_data.get("execution_id") or f"exec_{uuid.uuid4().hex[:8]}"
    created_at = execution_data.get("created_at") or datetime.now(timezone.utc).isoformat()

    record = {
        "id": exec_id,
        "execution_id": exec_id,
        "plan_id": execution_data.get("plan_id", ""),
        "workflow_id": execution_data.get("workflow_id", "demo"),
        "status": execution_data.get("status", "completed"),
        "actual_carbon": execution_data.get("total_actual_carbon", 0.0),
        "actual_cost": execution_data.get("total_actual_cost", 0.0),
        "actual_latency": execution_data.get("total_actual_latency", 0.0),
        "final_quality": execution_data.get("final_quality", 0.95),
        "node_results": execution_data.get("node_results", []),
        "escalations": execution_data.get("escalations", []),
        "created_at": created_at
    }

    _IN_MEMORY_STORE["executions"][exec_id] = record

    if DB_MODE != "memory":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO executions (id, plan_id, workflow_id, status, actual_carbon, actual_cost, actual_latency, final_quality, node_results, escalations, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["id"],
                    record["plan_id"],
                    record["workflow_id"],
                    record["status"],
                    record["actual_carbon"],
                    record["actual_cost"],
                    record["actual_latency"],
                    record["final_quality"],
                    json.dumps(record["node_results"]),
                    json.dumps(record["escalations"]),
                    record["created_at"]
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Repository Warning] SQLite save_execution error: {e}")

    return record


def get_executions_by_workflow(workflow_id: str) -> List[Dict[str, Any]]:
    execs = [e for e in _IN_MEMORY_STORE["executions"].values() if e.get("workflow_id") == workflow_id]

    if DB_MODE != "memory":
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, plan_id, workflow_id, status, actual_carbon, actual_cost, actual_latency, final_quality, node_results, escalations, created_at FROM executions WHERE workflow_id = ? ORDER BY created_at DESC",
                (workflow_id,)
            )
            rows = cursor.fetchall()
            conn.close()

            if rows:
                db_execs = []
                for row in rows:
                    db_execs.append({
                        "id": row[0],
                        "execution_id": row[0],
                        "plan_id": row[1],
                        "workflow_id": row[2],
                        "status": row[3],
                        "actual_carbon": row[4],
                        "actual_cost": row[5],
                        "actual_latency": row[6],
                        "final_quality": row[7],
                        "node_results": json.loads(row[8]),
                        "escalations": json.loads(row[9]),
                        "created_at": row[10]
                    })
                return db_execs
        except Exception as e:
            print(f"[Repository Warning] SQLite get_executions error: {e}")

    return execs

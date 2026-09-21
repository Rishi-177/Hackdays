"""
CarbonPilot Repository Layer

CRUD helper functions for workflows, execution plans, and execution history.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional


class WorkflowRepository:
    @staticmethod
    def create_workflow(
        conn: sqlite3.Connection,
        workflow_id: str,
        name: str,
        description: str,
        nodes: List[Dict[str, Any]],
        created_at: str,
    ) -> Dict[str, Any]:
        cursor = conn.cursor()
        nodes_json = json.dumps(nodes)
        cursor.execute(
            """
            INSERT INTO workflows (workflow_id, name, description, nodes_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (workflow_id, name, description, nodes_json, created_at),
        )
        conn.commit()
        return {
            "workflow_id": workflow_id,
            "name": name,
            "description": description,
            "nodes": nodes,
            "created_at": created_at,
        }

    @staticmethod
    def get_workflow(conn: sqlite3.Connection, workflow_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT workflow_id, name, description, nodes_json, created_at FROM workflows WHERE workflow_id = ?",
            (workflow_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "workflow_id": row["workflow_id"],
            "name": row["name"],
            "description": row["description"],
            "nodes": json.loads(row["nodes_json"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def list_workflows(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute("SELECT workflow_id, name, description, nodes_json, created_at FROM workflows ORDER BY created_at DESC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append(
                {
                    "workflow_id": r["workflow_id"],
                    "name": r["name"],
                    "description": r["description"],
                    "nodes": json.loads(r["nodes_json"]),
                    "created_at": r["created_at"],
                }
            )
        return result


class PlanRepository:
    @staticmethod
    def save_plan(
        conn: sqlite3.Connection,
        plan_id: str,
        workflow_id: str,
        baseline: Dict[str, Any],
        optimized: Dict[str, Any],
        savings: Dict[str, Any],
        reasoning: List[str],
        created_at: str,
    ) -> Dict[str, Any]:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO execution_plans (plan_id, workflow_id, baseline_json, optimized_json, savings_json, reasoning_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                workflow_id,
                json.dumps(baseline),
                json.dumps(optimized),
                json.dumps(savings),
                json.dumps(reasoning),
                created_at,
            ),
        )
        conn.commit()
        return {
            "plan_id": plan_id,
            "workflow_id": workflow_id,
            "baseline": baseline,
            "optimized": optimized,
            "savings": savings,
            "reasoning": reasoning,
            "created_at": created_at,
        }

    @staticmethod
    def get_plan(conn: sqlite3.Connection, plan_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT plan_id, workflow_id, baseline_json, optimized_json, savings_json, reasoning_json, created_at
            FROM execution_plans WHERE plan_id = ?
            """,
            (plan_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "plan_id": row["plan_id"],
            "workflow_id": row["workflow_id"],
            "baseline": json.loads(row["baseline_json"]),
            "optimized": json.loads(row["optimized_json"]),
            "savings": json.loads(row["savings_json"]),
            "reasoning": json.loads(row["reasoning_json"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def get_latest_plan_for_workflow(conn: sqlite3.Connection, workflow_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT plan_id, workflow_id, baseline_json, optimized_json, savings_json, reasoning_json, created_at
            FROM execution_plans WHERE workflow_id = ? ORDER BY created_at DESC LIMIT 1
            """,
            (workflow_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "plan_id": row["plan_id"],
            "workflow_id": row["workflow_id"],
            "baseline": json.loads(row["baseline_json"]),
            "optimized": json.loads(row["optimized_json"]),
            "savings": json.loads(row["savings_json"]),
            "reasoning": json.loads(row["reasoning_json"]),
            "created_at": row["created_at"],
        }


class ExecutionRepository:
    @staticmethod
    def save_execution(
        conn: sqlite3.Connection,
        execution_id: str,
        plan_id: str,
        workflow_id: str,
        status: str,
        total_carbon: float,
        total_cost: float,
        total_latency: float,
        final_quality: float,
        node_results: List[Dict[str, Any]],
        escalations: List[Dict[str, Any]],
        executed_at: str,
    ) -> Dict[str, Any]:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO executions (
                execution_id, plan_id, workflow_id, status,
                total_carbon, total_cost, total_latency, final_quality,
                results_json, escalations_json, executed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                plan_id,
                workflow_id,
                status,
                total_carbon,
                total_cost,
                total_latency,
                final_quality,
                json.dumps(node_results),
                json.dumps(escalations),
                executed_at,
            ),
        )
        conn.commit()
        return {
            "execution_id": execution_id,
            "plan_id": plan_id,
            "workflow_id": workflow_id,
            "status": status,
            "total_actual_carbon": total_carbon,
            "total_actual_cost": total_cost,
            "total_actual_latency": total_latency,
            "final_quality": final_quality,
            "node_results": node_results,
            "escalations": escalations,
            "executed_at": executed_at,
        }

    @staticmethod
    def get_executions_for_workflow(conn: sqlite3.Connection, workflow_id: str) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT execution_id, plan_id, workflow_id, status,
                   total_carbon, total_cost, total_latency, final_quality,
                   results_json, escalations_json, executed_at
            FROM executions WHERE workflow_id = ? ORDER BY executed_at DESC
            """,
            (workflow_id,),
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append(
                {
                    "execution_id": r["execution_id"],
                    "plan_id": r["plan_id"],
                    "workflow_id": r["workflow_id"],
                    "status": r["status"],
                    "total_actual_carbon": r["total_carbon"],
                    "total_actual_cost": r["total_cost"],
                    "total_actual_latency": r["total_latency"],
                    "final_quality": r["final_quality"],
                    "node_results": json.loads(r["results_json"]),
                    "escalations": json.loads(r["escalations_json"]),
                    "executed_at": r["executed_at"],
                }
            )
        return result

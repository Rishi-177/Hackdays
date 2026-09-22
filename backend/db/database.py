"""
Database Layer supporting SQLite / In-Memory local storage with optional Supabase PostgreSQL.
"""

import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DB_FILE = os.getenv("DATABASE_FILE", "carbonpilot.db")
DB_MODE = os.getenv("DB_MODE", "sqlite").lower()

# In-memory storage fallback for zero-dependency execution
_IN_MEMORY_STORE: Dict[str, Dict[str, Any]] = {
    "workflows": {},
    "execution_plans": {},
    "executions": {}
}

# Pre-populate demo market-research workflow in storage
DEMO_WORKFLOW = {
    "id": "demo",
    "name": "Market Research Report Generator",
    "description": "AI Market research DAG workflow simulating real-world document processing",
    "dag": {
        "nodes": [
            {"node_id": "retrieve", "name": "Retrieve Documents", "required_quality": 0.90},
            {"node_id": "summarize", "name": "Summarize Context", "required_quality": 0.90},
            {"node_id": "analysis_a", "name": "Financial Analysis", "required_quality": 0.95},
            {"node_id": "analysis_b", "name": "Market Analysis", "required_quality": 0.95},
            {"node_id": "report", "name": "Generate Final Report", "required_quality": 0.95}
        ],
        "edges": [
            {"source": "retrieve", "target": "summarize"},
            {"source": "summarize", "target": "analysis_a"},
            {"source": "summarize", "target": "analysis_b"},
            {"source": "analysis_a", "target": "report"},
            {"source": "analysis_b", "target": "report"}
        ]
    },
    "created_at": datetime.now(timezone.utc).isoformat()
}

_IN_MEMORY_STORE["workflows"]["demo"] = DEMO_WORKFLOW


def init_db():
    """Initializes SQLite database tables if using SQLite mode."""
    if DB_MODE == "memory":
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            dag TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS execution_plans (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            baseline TEXT NOT NULL,
            optimized TEXT NOT NULL,
            savings TEXT NOT NULL,
            reasoning TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS executions (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            actual_carbon REAL NOT NULL,
            actual_cost REAL NOT NULL,
            actual_latency REAL NOT NULL,
            final_quality REAL NOT NULL,
            node_results TEXT NOT NULL,
            escalations TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # Insert demo workflow into SQLite if missing
        cursor.execute("SELECT id FROM workflows WHERE id = ?", ("demo",))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO workflows (id, name, description, dag, created_at) VALUES (?, ?, ?, ?, ?)",
                ("demo", DEMO_WORKFLOW["name"], DEMO_WORKFLOW["description"], json.dumps(DEMO_WORKFLOW["dag"]), DEMO_WORKFLOW["created_at"])
            )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[CarbonPilot DB] SQLite initialization warning: {e}. Falling back to in-memory store.")


# Auto-initialize database schema on import
init_db()

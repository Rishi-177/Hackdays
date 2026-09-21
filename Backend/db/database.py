"""
CarbonPilot Database Connection & Initializer

Provides local SQLite database connection with in-memory fallback
and table initialization.
"""

import os
import sqlite3
from typing import Generator

DB_PATH = os.getenv("SQLITE_DB_PATH", os.getenv("DATABASE_URL", "carbonpilot.db"))

# Handle sqlite:/// prefix if provided in env
if DB_PATH.startswith("sqlite:///"):
    DB_PATH = DB_PATH.replace("sqlite:///", "")


def get_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS workflows (
            workflow_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            nodes_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_plans (
            plan_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            baseline_json TEXT NOT NULL,
            optimized_json TEXT NOT NULL,
            savings_json TEXT NOT NULL,
            reasoning_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS executions (
            execution_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL,
            total_carbon REAL NOT NULL,
            total_cost REAL NOT NULL,
            total_latency REAL NOT NULL,
            final_quality REAL NOT NULL,
            results_json TEXT NOT NULL,
            escalations_json TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            FOREIGN KEY (plan_id) REFERENCES execution_plans(plan_id),
            FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
        );
        """
    )

    conn.commit()
    conn.close()


def get_db_session() -> Generator[sqlite3.Connection, None, None]:
    """Dependency generator for FastAPI routes."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

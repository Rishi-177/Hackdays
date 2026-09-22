"""
Top-level compatibility shim for database.py (Donut Challenge).
"""

from backend.db.async_database import (
    Base,
    engine,
    AsyncSessionLocal,
    get_db,
    init_db,
    get_async_db,
    init_async_db,
    QUEUE_DB_URL as DATABASE_URL,
)

__all__ = [
    "Base",
    "engine",
    "AsyncSessionLocal",
    "get_db",
    "init_db",
    "get_async_db",
    "init_async_db",
    "DATABASE_URL",
]

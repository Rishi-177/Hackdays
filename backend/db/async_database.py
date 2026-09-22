"""
Asynchronous Database Layer using SQLAlchemy and aiosqlite for CarbonPilot Workflow Queue.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

QUEUE_DB_URL = os.getenv("QUEUE_DATABASE_URL", "sqlite+aiosqlite:///./workflows.db")

engine = create_async_engine(QUEUE_DB_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_async_db():
    """FastAPI dependency for async database sessions."""
    async with AsyncSessionLocal() as session:
        yield session


# Alias matching the prompt's dependency name
get_db = get_async_db


async def init_async_db():
    """Initializes the database tables asynchronously."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


init_db = init_async_db

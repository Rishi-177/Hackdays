"""
SQLAlchemy Models for Persistent Workflow Queue and Offline Sync.
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from backend.db.async_database import Base


class WorkflowQueue(Base):
    """
    Workflow queue table storing queued workflows, idempotency keys,
    offline state flags, retry counts, and execution results.
    """
    __tablename__ = "workflow_queue"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String, unique=True, index=True, nullable=False)  # Idempotency key
    payload = Column(JSON, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    is_offline = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    retry_count = Column(Integer, default=0)
    error_message = Column(String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "is_offline": self.is_offline,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "result": self.payload.get("result") if isinstance(self.payload, dict) else None,
        }

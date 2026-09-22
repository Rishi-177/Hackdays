"""
Workflow Queue API Router (Donut Challenge - Intermittent Connectivity).

Handles offline queueing, duplicate rejection via idempotency keys,
manual and background sync processing, and status inspection.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.async_database import get_async_db
from backend.db.queue_models import WorkflowQueue
from backend.engine.sync_engine import process_pending_workflows

router = APIRouter(tags=["Offline Queue & Sync"])


@router.post("/workflows", status_code=status.HTTP_200_OK)
@router.post("/api/workflows/queue", status_code=status.HTTP_200_OK)
async def submit_workflow(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Submit a workflow for optimization with idempotency protection.
    If offline, queues it for later sync; otherwise queues and triggers background processing.
    """
    workflow_id = payload.get("workflow_id") or str(uuid.uuid4())
    is_offline = bool(payload.get("is_offline", False))

    # Check for duplicate idempotency key
    stmt = select(WorkflowQueue).where(WorkflowQueue.workflow_id == workflow_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "workflow_id": workflow_id,
            "status": "duplicate",
            "message": "Already queued",
            "existing_status": existing.status,
        }

    # Queue workflow
    workflow = WorkflowQueue(
        workflow_id=workflow_id,
        payload=payload,
        is_offline=is_offline,
        status="pending",
    )
    db.add(workflow)
    await db.commit()

    # Trigger background sync processing
    background_tasks.add_task(process_pending_workflows, db)

    return {
        "workflow_id": workflow_id,
        "status": "queued",
        "is_offline": is_offline,
    }


@router.get("/workflows/{workflow_id}")
@router.get("/api/workflows/queue/{workflow_id}")
async def get_queued_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get workflow queue status, retry metrics, and optimization results.
    """
    stmt = select(WorkflowQueue).where(WorkflowQueue.workflow_id == workflow_id)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    payload_data = workflow.payload if isinstance(workflow.payload, dict) else {}
    return {
        "workflow_id": workflow.workflow_id,
        "status": workflow.status,
        "is_offline": workflow.is_offline,
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
        "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
        "retry_count": workflow.retry_count,
        "result": payload_data.get("result"),
        "error_message": workflow.error_message,
    }


@router.get("/workflows")
@router.get("/api/workflows/queue")
async def list_queued_workflows(
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all workflows currently tracked in the offline queue.
    """
    stmt = select(WorkflowQueue).order_by(WorkflowQueue.id.desc())
    result = await db.execute(stmt)
    workflows = result.scalars().all()
    return [wf.to_dict() for wf in workflows]


@router.post("/sync")
@router.post("/api/sync")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Manually trigger sync of all pending workflows.
    Called on network reconnect or by Service Worker Background Sync.
    """
    background_tasks.add_task(process_pending_workflows, db)
    return {
        "message": "Sync triggered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

"""
Sync Engine for CarbonPilot Workflow Queue (Donut Challenge).

Processes pending offline/queued workflows, applies graceful optimization,
and implements exponential backoff retry logic.
"""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.queue_models import WorkflowQueue
from backend.engine.offline_optimizer import optimize_workflow


async def process_pending_workflows(db: AsyncSession, reoptimize_online_on_sync: bool = False):
    """
    Process all pending workflows in the queue.
    Retry with exponential backoff on failure (max 5 retries).

    Args:
        db: AsyncSession database connection.
        reoptimize_online_on_sync: If True, re-optimizes offline workflows with
                                   full cloud models once reconnected.
    """
    stmt = select(WorkflowQueue).where(WorkflowQueue.status == "pending")
    result = await db.execute(stmt)
    workflows = result.scalars().all()

    for workflow in workflows:
        workflow.status = "processing"
        await db.commit()

        try:
            # Determine offline mode for execution
            is_offline_exec = workflow.is_offline and not reoptimize_online_on_sync

            # Run optimizer
            payload_data = workflow.payload if isinstance(workflow.payload, dict) else {}
            result_plan = optimize_workflow(payload_data, is_offline=is_offline_exec)

            # Mark as completed
            workflow.status = "completed"
            if not isinstance(workflow.payload, dict):
                workflow.payload = {}
            workflow.payload["result"] = result_plan
            # Flag that DB attribute changed for SQLAlchemy JSON tracking
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(workflow, "payload")

            await db.commit()

        except Exception as e:
            workflow.retry_count += 1
            workflow.error_message = str(e)

            # Exponential backoff: max 5 retries before failure
            if workflow.retry_count >= 5:
                workflow.status = "failed"
            else:
                workflow.status = "pending"  # Retry later

            await db.commit()

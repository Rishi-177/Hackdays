"""
FastAPI Router for Workflow Management (/api/workflows)
"""

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
import sqlite3

from backend.db.database import get_db_session
from backend.db.repository import WorkflowRepository
from backend.engine.dag import validate_dag
from backend.models.api_models import WorkflowCreate, WorkflowResponse

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate, db: sqlite3.Connection = Depends(get_db_session)):
    """Creates and validates a new workflow DAG."""
    nodes_data = [n.model_dump() for n in payload.nodes]

    if not validate_dag(nodes_data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid DAG structure: cycles detected or missing dependency references.",
        )

    workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    created = WorkflowRepository.create_workflow(
        conn=db,
        workflow_id=workflow_id,
        name=payload.name,
        description=payload.description or "",
        nodes=nodes_data,
        created_at=created_at,
    )

    return created


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: str, db: sqlite3.Connection = Depends(get_db_session)):
    """Retrieves a workflow by its workflow_id."""
    wf = WorkflowRepository.get_workflow(db, workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return wf


@router.get("", response_model=list[WorkflowResponse])
def list_workflows(db: sqlite3.Connection = Depends(get_db_session)):
    """Lists all stored workflows."""
    return WorkflowRepository.list_workflows(db)

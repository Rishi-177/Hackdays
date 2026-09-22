"""
Workflows API Router.
"""

from fastapi import APIRouter, HTTPException, status
from backend.models.api_models import WorkflowCreate, WorkflowResponse
from backend.db.repository import save_workflow, get_workflow, DEMO_WORKFLOW

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate):
    """Creates a new DAG workflow and persists it."""
    if not payload.dag or "nodes" not in payload.dag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workflow payload: DAG must contain a 'nodes' list."
        )

    saved_wf = save_workflow(payload.model_dump())
    return WorkflowResponse(**saved_wf)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow_by_id(workflow_id: str):
    """Retrieves stored workflow by ID (defaults to built-in 'demo' market research DAG)."""
    wf = get_workflow(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found."
        )
    return WorkflowResponse(**wf)

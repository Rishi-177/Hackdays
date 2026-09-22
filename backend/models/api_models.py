"""
Pydantic API Request/Response Models for CarbonPilot.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = Field(..., example="Market Research Report Generator")
    description: Optional[str] = Field(None, example="AI Market research DAG workflow")
    dag: Dict[str, Any] = Field(
        ...,
        example={
            "nodes": [
                {"node_id": "retrieve", "name": "Retrieve Documents"},
                {"node_id": "summarize", "name": "Summarize Context"},
                {"node_id": "analysis_a", "name": "Financial Analysis"},
                {"node_id": "analysis_b", "name": "Market Analysis"},
                {"node_id": "report", "name": "Generate Final Report"}
            ],
            "edges": [
                {"source": "retrieve", "target": "summarize"},
                {"source": "summarize", "target": "analysis_a"},
                {"source": "summarize", "target": "analysis_b"},
                {"source": "analysis_a", "target": "report"},
                {"source": "analysis_b", "target": "report"}
            ]
        }
    )


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    dag: Dict[str, Any]
    created_at: str


class OptimizeRequest(BaseModel):
    workflow_id: Optional[str] = Field("demo", description="ID of stored workflow or 'demo'")
    carbon_budget: float = Field(200.0, description="Hard carbon budget constraint in g CO2e")
    deadline_seconds: float = Field(1200.0, description="Hard execution deadline in seconds")
    quality_requirement: float = Field(0.95, description="Target quality score requirement (0.0 - 1.0)")
    carbon_weight: float = Field(0.8, description="Weight for carbon optimization priority (0.0 - 1.0)")
    latency_weight: float = Field(0.5, description="Weight for latency optimization priority (0.0 - 1.0)")
    cost_weight: float = Field(0.4, description="Weight for cost optimization priority (0.0 - 1.0)")
    workflow_dag: Optional[Dict[str, Any]] = None


class SavingsMetrics(BaseModel):
    carbon_percent: float
    cost_percent: float
    latency_percent: float


class OptimizeResponse(BaseModel):
    plan_id: str
    workflow_id: str
    baseline: Dict[str, Any]
    optimized: Dict[str, Any]
    savings: SavingsMetrics
    reasoning: List[str]


class ExecuteRequest(BaseModel):
    seed: Optional[int] = Field(42, description="Optional seed for deterministic simulation")
    forced_quality_overrides: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional dict mapping node_id -> forced quality score to simulate quality gate failure"
    )


class ExecuteResponse(BaseModel):
    execution_id: str
    plan_id: str
    status: str
    total_actual_carbon: float
    total_actual_cost: float
    total_actual_latency: float
    final_quality: float
    node_results: List[Dict[str, Any]]
    escalations: List[Dict[str, Any]]


class QualityCheckRequest(BaseModel):
    node: Any = Field(..., description="Node configuration dict or string identifier")
    output: Any = Field(..., description="Output payload or score from node execution")
    required_quality: float = Field(0.90, description="Required quality threshold (0.0 - 1.0)")
    seed: Optional[int] = None


class QualityCheckResponse(BaseModel):
    quality_score: float
    required_quality: float
    passed: bool
    action: str


class DashboardResponse(BaseModel):
    workflow_id: str
    baseline: Dict[str, Any]
    optimized: Dict[str, Any]
    savings: SavingsMetrics
    nodes: List[Dict[str, Any]]
    execution_history: List[Dict[str, Any]]

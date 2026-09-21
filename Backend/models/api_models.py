"""
CarbonPilot Pydantic Schemas for API Requests & Responses
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodeSchema(BaseModel):
    node_id: str = Field(..., description="Unique identifier for the node")
    model: str = Field(default="EfficientModel", description="AI model tier assigned")
    region: str = Field(default="Region-B", description="Execution cloud region")
    required_quality: float = Field(default=0.90, ge=0.0, le=1.0, description="Target quality score threshold")
    dependencies: List[str] = Field(default_factory=list, description="List of parent node_ids")
    predicted_latency: Optional[float] = Field(default=None, description="Estimated execution latency in seconds")
    predicted_carbon: Optional[float] = Field(default=None, description="Estimated carbon footprint in g CO2e")
    predicted_cost: Optional[float] = Field(default=None, description="Estimated cost in USD")


class WorkflowCreate(BaseModel):
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(default="", description="Workflow description")
    nodes: List[NodeSchema] = Field(..., description="DAG node definitions")


class WorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    description: str
    nodes: List[NodeSchema]
    created_at: str


class OptimizeRequest(BaseModel):
    workflow_id: str = Field(..., description="ID of the target workflow to optimize")
    carbon_budget: float = Field(default=200.0, ge=0.0, description="Hard carbon budget limit in g CO2e")
    deadline_seconds: float = Field(default=1200.0, ge=0.0, description="Hard execution deadline in seconds")
    quality_requirement: float = Field(default=0.95, ge=0.0, le=1.0, description="Required target quality score")
    carbon_weight: float = Field(default=0.8, ge=0.0, le=1.0, description="Priority weight for carbon reduction")
    latency_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Priority weight for latency reduction")
    cost_weight: float = Field(default=0.4, ge=0.0, le=1.0, description="Priority weight for cost reduction")


class PlanMetrics(BaseModel):
    carbon: float = Field(..., description="Total carbon footprint in g CO2e")
    cost: float = Field(..., description="Total execution cost in USD")
    latency: float = Field(..., description="Estimated total workflow latency in seconds")
    quality: float = Field(..., description="Average predicted quality score")
    ai_calls: int = Field(..., description="Number of AI model invocations")
    region_distribution: Dict[str, int] = Field(..., description="Count of nodes per region")
    model_distribution: Dict[str, int] = Field(..., description="Count of nodes per model")
    nodes: List[Dict[str, Any]] = Field(..., description="Detailed node execution plan")


class Savings(BaseModel):
    carbon_percent: float = Field(..., description="Percentage carbon reduction")
    cost_percent: float = Field(..., description="Percentage cost reduction")
    latency_percent: float = Field(..., description="Percentage latency reduction")
    carbon_saved_g: float = Field(..., description="Absolute carbon saved in g CO2e")
    cost_saved_usd: float = Field(..., description="Absolute cost saved in USD")
    time_saved_sec: float = Field(..., description="Absolute time saved in seconds")


class OptimizeResponse(BaseModel):
    plan_id: str
    workflow_id: str
    baseline: PlanMetrics
    optimized: PlanMetrics
    savings: Savings
    reasoning: List[str] = Field(..., description="Plain-English explanation of optimizer choices")


class ExecuteRequest(BaseModel):
    plan_id: Optional[str] = Field(default=None, description="Plan ID to execute")
    random_seed: Optional[int] = Field(default=None, description="Optional random seed for simulation reproducibility")
    force_quality_fail_nodes: Optional[List[str]] = Field(default=None, description="Nodes to force Quality Gate failure on")


class ExecuteResponse(BaseModel):
    execution_id: str
    plan_id: str
    workflow_id: str
    status: str
    node_results: List[Dict[str, Any]]
    total_actual_carbon: float
    total_actual_cost: float
    total_actual_latency: float
    final_quality: float
    escalations: List[Dict[str, Any]]
    executed_at: str


class QualityCheckRequest(BaseModel):
    node: Dict[str, Any] = Field(..., description="Node configuration")
    output: Optional[Dict[str, Any]] = Field(default=None, description="Node execution output or quality payload")
    required_quality: Optional[float] = Field(default=0.90, description="Target quality score")


class QualityCheckResponse(BaseModel):
    quality_score: float
    required_quality: float
    passed: bool
    action: str


class DashboardResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    baseline_metrics: Dict[str, Any]
    carbonpilot_metrics: Dict[str, Any]
    savings: Dict[str, Any]
    node_information: List[Dict[str, Any]]
    execution_history: List[Dict[str, Any]]

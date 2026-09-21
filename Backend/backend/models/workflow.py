"""Workflow and Optimization data models for CarbonPilot.

Provides Pydantic models for nodes, workflows, optimization constraints,
and structured optimization results.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class WorkflowNode(BaseModel):
    """Represents a discrete task or step in an AI workflow DAG."""

    id: str = Field(..., description="Unique identifier for the node")
    name: str = Field(..., description="Human-readable name of the step")
    type: str = Field(
        ...,
        description="Type of task (e.g., 'retrieval', 'llm', 'analysis', 'report', 'filter')",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="IDs of predecessor nodes that must finish before this node",
    )
    required_quality: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality threshold (0.0 to 1.0)",
    )
    priority: Union[int, str] = Field(
        default=1,
        description="Execution priority (integer or label e.g., 'high', 'medium', 'low')",
    )
    estimated_tokens: int = Field(
        default=1000,
        ge=0,
        description="Estimated token load (input + output) for the operation",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional metadata (e.g., prompt keys, parameters, cache tags)",
    )

    def is_compatible_for_fusion_with(self, other: "WorkflowNode") -> bool:
        """Checks whether this node and another node can be fused into a single prompt step."""
        fusable_types = {"llm", "analysis", "summary", "summarize", "transform", "report"}
        return (
            self.type.lower() in fusable_types
            and other.type.lower() in fusable_types
            and self.metadata.get("disable_fusion") is not True
            and other.metadata.get("disable_fusion") is not True
        )


class Workflow(BaseModel):
    """Represents an entire AI workflow defined as a Directed Acyclic Graph (DAG)."""

    id: str = Field(..., description="Unique workflow identifier")
    name: str = Field(..., description="Human-readable workflow name")
    nodes: List[WorkflowNode] = Field(
        default_factory=list, description="List of nodes forming the workflow graph"
    )

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Lookup a node by its unique ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    @property
    def node_ids(self) -> List[str]:
        """Return list of all node IDs."""
        return [node.id for node in self.nodes]

    def clone(self) -> "Workflow":
        """Deep-copy workflow model."""
        return Workflow.model_validate(self.model_dump())


class OptimizationConstraints(BaseModel):
    """Constraints and priority weights for whole-workflow optimization."""

    carbon_budget: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Hard maximum carbon emission cap in grams CO2e",
    )
    deadline: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Hard maximum execution deadline in seconds",
    )
    quality_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Global minimum acceptable quality threshold",
    )
    carbon_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight factor for carbon footprint optimization",
    )
    latency_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight factor for latency optimization",
    )
    cost_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight factor for monetary cost optimization",
    )
    priority_mode: str = Field(
        default="balanced",
        description="High-level strategy mode: 'balanced', 'carbon', 'latency', 'cost'",
    )
    enable_fusion: bool = Field(
        default=True,
        description="Allow fusing sequential compatible LLM operations",
    )
    enable_pruning: bool = Field(
        default=True,
        description="Allow pruning duplicate or dead-end redundant operations",
    )


class MetricSnapshot(BaseModel):
    """Estimated metrics for an execution plan or workflow configuration."""

    total_nodes: int
    total_tokens: int
    critical_path_latency_sec: float
    sequential_latency_sec: float
    estimated_carbon_g_co2: float
    estimated_cost_usd: float
    average_quality: float
    parallel_levels: int


class OptimizationImprovement(BaseModel):
    """Comparative delta between baseline and optimized workflows."""

    latency_reduction_pct: float
    carbon_reduction_pct: float
    cost_reduction_pct: float
    token_reduction_pct: float
    baseline_metrics: MetricSnapshot
    optimized_metrics: MetricSnapshot


class OptimizationResult(BaseModel):
    """Complete structured response returned by optimize_workflow."""

    baseline_workflow: Dict[str, Any]
    optimized_workflow: Dict[str, Any]
    baseline_node_count: int
    optimized_node_count: int
    parallel_groups: List[List[str]]
    removed_nodes: List[Dict[str, Any]]
    combined_nodes: List[Dict[str, Any]]
    estimated_improvement: OptimizationImprovement
    explanations: List[str]

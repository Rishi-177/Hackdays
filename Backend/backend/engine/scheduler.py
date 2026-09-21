"""Execution Scheduler and Multi-Objective Plan Selector for CarbonPilot.

Generates candidate execution plans (model, region, and timing combinations),
enforces hard constraints (carbon budget, deadline, and quality), calculates
deadline slack, and selects the optimal plan using deterministic multi-objective scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.engine.carbon import (
    calculate_node_carbon,
    calculate_node_cost,
    calculate_node_latency,
    calculate_slack,
    calculate_total_carbon,
    check_carbon_budget,
    load_model_profiles,
    load_region_profiles,
)
from backend.engine.dag import WorkflowDAG
from backend.models.workflow import Workflow, WorkflowNode


@dataclass
class NodeAssignment:
    """Execution parameters assigned to a single workflow node."""

    node_id: str
    node_name: str
    model: str
    region: str
    latency_sec: float
    carbon_g: float
    cost_usd: float
    quality: float


@dataclass
class CandidatePlan:
    """A complete candidate execution plan across the entire workflow DAG."""

    name: str
    strategy: str
    node_assignments: Dict[str, NodeAssignment]
    execution_delay_sec: float = 0.0
    schedule_mode: str = "immediate"  # 'immediate' or 'delayed_green_window'
    total_carbon_g: float = 0.0
    total_cost_usd: float = 0.0
    critical_path_latency_sec: float = 0.0
    total_latency_sec: float = 0.0
    average_quality: float = 0.0
    is_valid: bool = True
    rejection_reasons: List[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert candidate plan to JSON-serializable dictionary."""
        return {
            "name": self.name,
            "strategy": self.strategy,
            "schedule_mode": self.schedule_mode,
            "execution_delay_sec": self.execution_delay_sec,
            "node_assignments": {
                nid: {
                    "node_id": na.node_id,
                    "node_name": na.node_name,
                    "model": na.model,
                    "region": na.region,
                    "latency_sec": na.latency_sec,
                    "carbon_g": na.carbon_g,
                    "cost_usd": na.cost_usd,
                    "quality": na.quality,
                }
                for nid, na in self.node_assignments.items()
            },
            "total_carbon_g": self.total_carbon_g,
            "total_cost_usd": self.total_cost_usd,
            "critical_path_latency_sec": self.critical_path_latency_sec,
            "total_latency_sec": self.total_latency_sec,
            "average_quality": self.average_quality,
            "is_valid": self.is_valid,
            "rejection_reasons": self.rejection_reasons,
            "score": round(self.score, 4),
        }


def _evaluate_candidate(
    name: str,
    strategy: str,
    assignments_spec: Dict[str, Tuple[str, str]],  # node_id -> (model, region)
    dag: WorkflowDAG,
    delay_sec: float = 0.0,
    is_green_window: bool = False,
) -> CandidatePlan:
    """Evaluates an assignment configuration and computes its critical path and total metrics."""
    models = load_model_profiles()
    node_assignments: Dict[str, NodeAssignment] = {}
    total_cost = 0.0
    total_carbon = 0.0
    qualities: List[float] = []

    for nid, node in dag.nodes_by_id.items():
        model_id, region_id = assignments_spec.get(nid, ("BalancedModel", "Region-C"))
        m_info = models.get(model_id, models.get("BalancedModel", {}))
        m_qual = float(m_info.get("quality", 0.90))

        node_lat = calculate_node_latency(model_id, region_id, node.estimated_tokens)
        node_carb = calculate_node_carbon(
            model_id, region_id, node.estimated_tokens, is_green_window=is_green_window
        )
        node_cost = calculate_node_cost(model_id, node.estimated_tokens)

        node_assignments[nid] = NodeAssignment(
            node_id=nid,
            node_name=node.name,
            model=model_id,
            region=region_id,
            latency_sec=node_lat,
            carbon_g=node_carb,
            cost_usd=node_cost,
            quality=m_qual,
        )
        total_cost += node_cost
        total_carbon += node_carb
        qualities.append(m_qual)

    # Compute critical path latency across the DAG for this specific assignment
    def plan_latency_fn(node: WorkflowNode) -> float:
        return node_assignments[node.id].latency_sec

    _, crit_lat = dag.compute_critical_path(latency_fn=plan_latency_fn)
    total_lat = round(crit_lat + delay_sec, 2)
    avg_qual = round(sum(qualities) / len(qualities), 3) if qualities else 0.0

    return CandidatePlan(
        name=name,
        strategy=strategy,
        node_assignments=node_assignments,
        execution_delay_sec=delay_sec,
        schedule_mode="delayed_green_window" if delay_sec > 0 else "immediate",
        total_carbon_g=round(total_carbon, 3),
        total_cost_usd=round(total_cost, 4),
        critical_path_latency_sec=crit_lat,
        total_latency_sec=total_lat,
        average_quality=avg_qual,
    )


def generate_candidate_plans(
    workflow: Workflow,
    deadline_seconds: Optional[float] = None,
) -> List[CandidatePlan]:
    """Generates distinct candidate plans representing different execution trade-offs."""
    dag = WorkflowDAG(workflow)
    models = load_model_profiles()
    regions = load_region_profiles()
    candidates: List[CandidatePlan] = []

    # 1. Strategy: All-Efficient in Low-Carbon EU-North (Region-B)
    spec_eco = {nid: ("EfficientModel", "Region-B") for nid in dag.nodes_by_id}
    candidates.append(
        _evaluate_candidate("Eco-Fast-B", "Eco / Low-Carbon", spec_eco, dag)
    )

    # 2. Strategy: Ultra-Fast Latency-Optimized in US-East (Region-A)
    spec_fast = {
        nid: (
            "EfficientModel" if dag.nodes_by_id[nid].type.lower() == "retrieval" else "BalancedModel",
            "Region-A",
        )
        for nid in dag.nodes_by_id
    }
    candidates.append(
        _evaluate_candidate("Speed-Focused-A", "Low-Latency", spec_fast, dag)
    )

    # 2b. Strategy: Fast Quality-Matched in US-East (Region-A)
    # Meets quality requirements while utilizing lowest-latency region for tight deadlines
    spec_smart_a: Dict[str, Tuple[str, str]] = {}
    for nid, node in dag.nodes_by_id.items():
        req_q = node.required_quality
        if node.type.lower() in {"retrieval", "cache", "data", "filter"} or req_q <= 0.88:
            m = "EfficientModel"
        elif req_q <= 0.93:
            m = "BalancedModel"
        else:
            m = "AdvancedModel"
        spec_smart_a[nid] = (m, "Region-A")

    candidates.append(
        _evaluate_candidate("Fast-Quality-A", "Low-Latency Quality-Matched", spec_smart_a, dag)
    )

    # 3. Strategy: Quality-Adaptive Smart Hybrid in Low-Carbon EU-North (Region-B)
    # Assigns minimal model required to satisfy each node's required_quality
    spec_smart_b: Dict[str, Tuple[str, str]] = {}
    for nid, node in dag.nodes_by_id.items():
        req_q = node.required_quality
        if node.type.lower() in {"retrieval", "cache", "data", "filter"} or req_q <= 0.88:
            m = "EfficientModel"
        elif req_q <= 0.93:
            m = "BalancedModel"
        else:
            m = "AdvancedModel"
        spec_smart_b[nid] = (m, "Region-B")

    candidates.append(
        _evaluate_candidate("Smart-Hybrid-B", "Carbon-Aware Quality-Matched", spec_smart_b, dag)
    )

    # 4. Strategy: Standard Balanced Workhorse in US-West (Region-C)
    spec_balanced_c = {nid: ("BalancedModel", "Region-C") for nid in dag.nodes_by_id}
    candidates.append(
        _evaluate_candidate("Standard-Balanced-C", "Balanced Standard", spec_balanced_c, dag)
    )

    # 5. Strategy: High-Fidelity Advanced in US-West (Region-C)
    spec_advanced = {
        nid: (
            "BalancedModel" if dag.nodes_by_id[nid].type.lower() == "retrieval" else "AdvancedModel",
            "Region-C",
        )
        for nid in dag.nodes_by_id
    }
    candidates.append(
        _evaluate_candidate("High-Fidelity-C", "Maximum Quality", spec_advanced, dag)
    )

    # 6. Green Window Slack Variants:
    # If sufficient deadline slack exists for Region-B's green window (300s wait),
    # generate delayed executions into the cleaner grid window!
    green_win_b = regions.get("Region-B", {}).get("green_window", {})
    if green_win_b and deadline_seconds is not None:
        wait_time = float(green_win_b.get("wait_seconds", 300))
        # Check if smart hybrid has slack
        smart_b_candidate = candidates[2]
        slack = calculate_slack(deadline_seconds, smart_b_candidate.critical_path_latency_sec)
        if slack is not None and slack >= wait_time:
            delayed_candidate = _evaluate_candidate(
                "Smart-Hybrid-B (Green Window)",
                "Carbon-Optimized Slack Delay",
                spec_smart_b,
                dag,
                delay_sec=wait_time,
                is_green_window=True,
            )
            candidates.append(delayed_candidate)

        # Also add eco delayed candidate if feasible
        eco_b_candidate = candidates[0]
        eco_slack = calculate_slack(deadline_seconds, eco_b_candidate.critical_path_latency_sec)
        if eco_slack is not None and eco_slack >= wait_time:
            delayed_eco = _evaluate_candidate(
                "Eco-Fast-B (Green Window)",
                "Ultra-Low Carbon Slack Delay",
                spec_eco,
                dag,
                delay_sec=wait_time,
                is_green_window=True,
            )
            candidates.append(delayed_eco)

    return candidates


def enforce_hard_constraints(
    candidates: List[CandidatePlan],
    workflow: Workflow,
    carbon_budget: Optional[float] = None,
    deadline_seconds: Optional[float] = None,
    quality_requirement: Optional[float] = None,
) -> None:
    """Evaluates hard constraints against each candidate, marking violations in-place."""
    models = load_model_profiles()

    for candidate in candidates:
        candidate.rejection_reasons = []

        # Constraint 1: Carbon Budget
        if carbon_budget is not None:
            if candidate.total_carbon_g > carbon_budget:
                excess = round(candidate.total_carbon_g - carbon_budget, 2)
                candidate.rejection_reasons.append(
                    f"Exceeds carbon budget ({candidate.total_carbon_g:.2f}g > {carbon_budget:.2f}g, excess {excess}g)."
                )

        # Constraint 2: Deadline
        if deadline_seconds is not None:
            if candidate.total_latency_sec > deadline_seconds:
                delay_str = f" including {candidate.execution_delay_sec}s slack wait" if candidate.execution_delay_sec > 0 else ""
                candidate.rejection_reasons.append(
                    f"Cannot satisfy deadline ({candidate.total_latency_sec:.2f}s{delay_str} > {deadline_seconds:.2f}s)."
                )

        # Constraint 3: Quality Threshold
        for nid, na in candidate.node_assignments.items():
            node = workflow.get_node(nid)
            min_q = node.required_quality if node else 0.85
            if quality_requirement is not None:
                min_q = max(min_q, quality_requirement)

            # Retrieval / non-LLM steps are utility nodes and don't require heavy LLM reasoning quality
            is_utility_node = node and node.type.lower() in {"retrieval", "cache", "data", "filter"}
            if not is_utility_node and na.quality < min_q:
                candidate.rejection_reasons.append(
                    f"Node '{na.node_name}' assigned {na.model} (quality {na.quality:.2f}) does not meet required quality {min_q:.2f}."
                )

        candidate.is_valid = len(candidate.rejection_reasons) == 0


def rank_and_score_plans(
    candidates: List[CandidatePlan],
    carbon_weight: float = 0.4,
    latency_weight: float = 0.3,
    cost_weight: float = 0.3,
    quality_weight: float = 0.1,
) -> List[CandidatePlan]:
    """Applies transparent deterministic multi-objective scoring to valid candidate plans."""
    valid_candidates = [c for c in candidates if c.is_valid]
    if not valid_candidates:
        # If no candidates are completely valid, score all candidates to find closest fit
        pool = candidates
    else:
        pool = valid_candidates

    # Compute min/max for normalization
    min_carb = min(c.total_carbon_g for c in pool)
    max_carb = max(c.total_carbon_g for c in pool)
    min_lat = min(c.total_latency_sec for c in pool)
    max_lat = max(c.total_latency_sec for c in pool)
    min_cost = min(c.total_cost_usd for c in pool)
    max_cost = max(c.total_cost_usd for c in pool)
    min_qual = min(c.average_quality for c in pool)
    max_qual = max(c.average_quality for c in pool)

    def norm(val: float, low: float, high: float) -> float:
        if high - low <= 1e-9:
            return 0.5
        return (val - low) / (high - low)

    for c in candidates:
        norm_c = norm(c.total_carbon_g, min_carb, max_carb)
        norm_l = norm(c.total_latency_sec, min_lat, max_lat)
        norm_cost = norm(c.total_cost_usd, min_cost, max_cost)
        # Higher quality is desirable, so penalty decreases as quality increases
        norm_q = 1.0 - norm(c.average_quality, min_qual, max_qual)

        # Multi-objective score: lower is better
        c.score = (
            carbon_weight * norm_c
            + latency_weight * norm_l
            + cost_weight * norm_cost
            + quality_weight * norm_q
        )

    # Sort valid candidates first, then by ascending score
    candidates.sort(key=lambda c: (not c.is_valid, c.score))
    return candidates


def generate_scheduler_reasoning(
    selected: CandidatePlan,
    candidates: List[CandidatePlan],
    carbon_budget: Optional[float],
    deadline_seconds: Optional[float],
    quality_requirement: Optional[float],
) -> List[str]:
    """Generates clear, human-readable explanations of scheduling decisions."""
    reasoning: List[str] = []

    # 1. Plan and Strategy
    reasoning.append(
        f"Selected plan '{selected.name}' ({selected.strategy}) with multi-objective score {selected.score:.3f}."
    )

    # 2. Timing & Slack
    if selected.schedule_mode == "delayed_green_window":
        reasoning.append(
            f"Execution delayed by {int(selected.execution_delay_sec)} seconds into a forecasted clean renewable grid window, reducing grid carbon intensity."
        )
    else:
        if deadline_seconds is not None:
            slack = calculate_slack(deadline_seconds, selected.total_latency_sec)
            reasoning.append(
                f"Immediate execution scheduled: completes in {selected.total_latency_sec:.2f}s with {slack:.2f}s of deadline slack."
            )
        else:
            reasoning.append(
                f"Immediate execution scheduled: estimated duration {selected.total_latency_sec:.2f}s."
            )

    # 3. Regional Placement
    regions_used = {na.region for na in selected.node_assignments.values()}
    if len(regions_used) == 1:
        reg = next(iter(regions_used))
        if reg == "Region-B":
            reasoning.append(
                "Region-B selected because its hydro/wind grid yields lowest carbon intensity."
            )
        elif reg == "Region-A":
            reasoning.append(
                "Region-A selected for minimal network latency overhead."
            )
        else:
            reasoning.append(
                f"Workloads deployed to {reg} balancing carbon intensity and network latency."
            )
    else:
        reasoning.append(f"Workloads distributed across regions: {', '.join(sorted(regions_used))}.")

    # 4. Model Selection
    models_used = {na.model for na in selected.node_assignments.values()}
    if "EfficientModel" in models_used and "AdvancedModel" not in models_used:
        reasoning.append(
            "EfficientModel prioritized for non-critical nodes because required quality can be satisfied at lower carbon and latency."
        )
    elif "AdvancedModel" in models_used:
        reasoning.append(
            "AdvancedModel selected for complex analysis steps to satisfy stringent quality requirements."
        )

    # 5. Carbon Budget Verification
    if carbon_budget is not None:
        budget_info = check_carbon_budget(selected.total_carbon_g, carbon_budget)
        if budget_info["within_budget"]:
            reasoning.append(
                f"Carbon budget satisfied: estimated {selected.total_carbon_g:.2f}g CO2e (remaining buffer: {budget_info['remaining']:.2f}g)."
            )
        else:
            reasoning.append(
                f"CRITICAL: Plan carbon ({selected.total_carbon_g:.2f}g) exceeds budget cap ({carbon_budget:.2f}g)."
            )

    # 6. Rejection of competing alternatives
    rejected_count = sum(1 for c in candidates if not c.is_valid)
    if rejected_count > 0:
        first_rejected = next(c for c in candidates if not c.is_valid)
        reasoning.append(
            f"Rejected {rejected_count} candidate plans due to hard constraints (e.g., '{first_rejected.name}' rejected: {first_rejected.rejection_reasons[0]})."
        )

    return reasoning


def create_execution_plan(
    workflow: Union[Workflow, Dict[str, Any]],
    carbon_budget: Optional[float] = None,
    deadline_seconds: Optional[float] = None,
    quality_requirement: Optional[float] = None,
    carbon_weight: float = 0.4,
    latency_weight: float = 0.3,
    cost_weight: float = 0.3,
    quality_weight: float = 0.1,
) -> Dict[str, Any]:
    """Main Scheduler Interface.

    Generates candidate execution plans, applies hard constraints, calculates deadline slack,
    and scores candidates using configurable multi-objective weights.

    Returns:
        {
            "selected_plan": ...,
            "estimated_carbon": ...,
            "estimated_cost": ...,
            "estimated_latency": ...,
            "estimated_quality": ...,
            "deadline_met": bool,
            "carbon_budget_met": bool,
            "reasoning": [...]
        }
    """
    # 1. Normalize Workflow input
    if isinstance(workflow, dict):
        wf = Workflow.model_validate(workflow)
    elif isinstance(workflow, Workflow):
        wf = workflow
    else:
        raise ValueError(f"Invalid workflow type: {type(workflow)}")

    # 2. Generate Candidate Plans
    candidates = generate_candidate_plans(wf, deadline_seconds=deadline_seconds)

    # 3. Enforce Hard Constraints
    enforce_hard_constraints(
        candidates,
        workflow=wf,
        carbon_budget=carbon_budget,
        deadline_seconds=deadline_seconds,
        quality_requirement=quality_requirement,
    )

    # 4. Multi-Objective Scoring & Ranking
    ranked_candidates = rank_and_score_plans(
        candidates,
        carbon_weight=carbon_weight,
        latency_weight=latency_weight,
        cost_weight=cost_weight,
        quality_weight=quality_weight,
    )

    best_plan = ranked_candidates[0]

    # 5. Evaluate Met Status
    deadline_met = (
        best_plan.total_latency_sec <= deadline_seconds
        if deadline_seconds is not None
        else True
    )
    budget_met = (
        best_plan.total_carbon_g <= carbon_budget
        if carbon_budget is not None
        else True
    )

    # 6. Generate Explainability Logs
    reasoning = generate_scheduler_reasoning(
        best_plan,
        candidates,
        carbon_budget=carbon_budget,
        deadline_seconds=deadline_seconds,
        quality_requirement=quality_requirement,
    )

    return {
        "selected_plan": best_plan.to_dict(),
        "candidate_plans": [c.to_dict() for c in candidates],
        "estimated_carbon": best_plan.total_carbon_g,
        "estimated_cost": best_plan.total_cost_usd,
        "estimated_latency": best_plan.total_latency_sec,
        "estimated_quality": best_plan.average_quality,
        "deadline_met": deadline_met,
        "carbon_budget_met": budget_met,
        "reasoning": reasoning,
    }

"""Whole-Workflow Optimizer for CarbonPilot.

Analyzes the entire workflow DAG to perform deterministic, explainable
optimizations: concurrency scheduling, redundant node pruning, and linear step fusion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.engine.dag import DAGValidationError, WorkflowDAG
from backend.models.workflow import (
    MetricSnapshot,
    OptimizationConstraints,
    OptimizationImprovement,
    OptimizationResult,
    Workflow,
    WorkflowNode,
)


def _compute_node_latency(node: WorkflowNode) -> float:
    """Estimates single-node execution latency in seconds.

    Retrieval / non-LLM operations have lower latency than LLM generation.
    """
    if node.type.lower() in {"retrieval", "cache", "filter", "data"}:
        return round(0.5 + (node.estimated_tokens / 2000.0) * 0.4, 2)
    # LLM / reasoning steps
    return round(1.0 + (node.estimated_tokens / 1000.0) * 1.2, 2)


def _compute_node_carbon(node: WorkflowNode) -> float:
    """Estimates carbon footprint (g CO2e) for a single node execution."""
    base_carbon = 0.05  # invocation overhead
    token_carbon = (node.estimated_tokens / 1000.0) * 0.22  # ~0.22g per 1k tokens
    return round(base_carbon + token_carbon, 3)


def _compute_node_cost(node: WorkflowNode) -> float:
    """Estimates monetary cost (USD) for a single node execution."""
    base_cost = 0.0005
    token_cost = (node.estimated_tokens / 1000.0) * 0.0025
    return round(base_cost + token_cost, 4)


def compute_workflow_metrics(dag: WorkflowDAG, is_parallel: bool = True) -> MetricSnapshot:
    """Computes comprehensive performance, carbon, and cost metrics for a DAG.

    Args:
        dag: The WorkflowDAG to evaluate.
        is_parallel: If True, latency is computed using critical path (concurrent execution).
                     If False (baseline default), latency is purely sequential.
    """
    nodes = list(dag.nodes_by_id.values())
    if not nodes:
        return MetricSnapshot(
            total_nodes=0,
            total_tokens=0,
            critical_path_latency_sec=0.0,
            sequential_latency_sec=0.0,
            estimated_carbon_g_co2=0.0,
            estimated_cost_usd=0.0,
            average_quality=0.0,
            parallel_levels=0,
        )

    total_tokens = sum(n.estimated_tokens for n in nodes)
    seq_latency = round(sum(_compute_node_latency(n) for n in nodes), 2)
    _, crit_latency = dag.compute_critical_path(latency_fn=_compute_node_latency)

    effective_latency = crit_latency if is_parallel else seq_latency
    total_carbon = round(sum(_compute_node_carbon(n) for n in nodes), 3)
    total_cost = round(sum(_compute_node_cost(n) for n in nodes), 4)
    avg_quality = round(sum(n.required_quality for n in nodes) / len(nodes), 3)
    stages = dag.get_parallel_stages()

    return MetricSnapshot(
        total_nodes=len(nodes),
        total_tokens=total_tokens,
        critical_path_latency_sec=crit_latency,
        sequential_latency_sec=seq_latency,
        estimated_carbon_g_co2=total_carbon,
        estimated_cost_usd=total_cost,
        average_quality=avg_quality,
        parallel_levels=len(stages),
    )


def _prune_redundant_nodes(
    dag: WorkflowDAG,
) -> Tuple[Workflow, List[Dict[str, Any]], List[str]]:
    """Identifies and removes duplicate or unneeded operations.

    Rule 1: Duplicate operations (identical type, identical dependencies, identical payload/name)
            are merged, redirecting downstream dependents to the canonical node.
    Rule 2: Nodes explicitly flagged with metadata={'redundant': True} or type='noop' are pruned.
    """
    current_wf = dag.workflow.clone()
    removed_log: List[Dict[str, Any]] = []
    explanations: List[str] = []

    # Map to detect duplicate tasks: (type, tuple(sorted(dependencies)), signature)
    seen_signatures: Dict[Tuple[str, Tuple[str, ...], str], str] = {}
    redirect_map: Dict[str, str] = {}
    nodes_to_keep: List[WorkflowNode] = []

    for node in current_wf.nodes:
        # Check explicit redundant flag
        if node.metadata.get("redundant") is True or node.type.lower() == "noop":
            removed_log.append(
                {
                    "node_id": node.id,
                    "name": node.name,
                    "reason": "Explicitly marked redundant or no-op operation",
                    "redirected_to": None,
                }
            )
            explanations.append(
                f"Pruned unneeded node '{node.name}' ({node.id}) to eliminate zero-value token and carbon waste."
            )
            continue

        # Signature: type, dependencies, and normalized task identifier
        dep_key = tuple(sorted(node.dependencies))
        task_sig = str(node.metadata.get("task_key", node.name.lower().strip()))
        full_key = (node.type.lower(), dep_key, task_sig)

        if full_key in seen_signatures:
            canonical_id = seen_signatures[full_key]
            redirect_map[node.id] = canonical_id
            removed_log.append(
                {
                    "node_id": node.id,
                    "name": node.name,
                    "reason": f"Duplicate operation of canonical node '{canonical_id}'",
                    "redirected_to": canonical_id,
                }
            )
            explanations.append(
                f"Identified duplicate {node.type} step '{node.name}' ({node.id}); pruned and redirected downstream dependencies to '{canonical_id}'."
            )
        else:
            seen_signatures[full_key] = node.id
            nodes_to_keep.append(node)

    # Rewire dependencies for surviving nodes
    pruned_nodes: List[WorkflowNode] = []
    surviving_ids = {n.id for n in nodes_to_keep}

    for node in nodes_to_keep:
        updated_deps: List[str] = []
        for dep in node.dependencies:
            # Follow redirection chain if needed
            resolved_dep = dep
            while resolved_dep in redirect_map:
                resolved_dep = redirect_map[resolved_dep]

            if resolved_dep in surviving_ids and resolved_dep not in updated_deps:
                updated_deps.append(resolved_dep)

        updated_node = node.model_copy(update={"dependencies": updated_deps})
        pruned_nodes.append(updated_node)

    pruned_wf = Workflow(
        id=current_wf.id, name=current_wf.name, nodes=pruned_nodes
    )
    return pruned_wf, removed_log, explanations


def _fuse_linear_steps(
    dag: WorkflowDAG,
) -> Tuple[Workflow, List[Dict[str, Any]], List[str]]:
    """Identifies linear sequential chains (A -> B) and fuses them into a single step.

    Conditions for fusion:
    - Node A has exactly ONE child: B.
    - Node B has exactly ONE dependency: A.
    - Both nodes are compatible for fusion (e.g. LLM/summarization/analysis).
    """
    fused_wf = dag.workflow.clone()
    combined_log: List[Dict[str, Any]] = []
    explanations: List[str] = []

    # Iterate until no more fusion candidates exist
    changed = True
    while changed:
        changed = False
        current_dag = WorkflowDAG(fused_wf)
        nodes_dict = {n.id: n for n in fused_wf.nodes}

        for node_a_id in current_dag.get_topological_order():
            node_a = nodes_dict.get(node_a_id)
            if not node_a:
                continue

            children = current_dag.adj[node_a_id]
            if len(children) == 1:
                node_b_id = next(iter(children))
                node_b = nodes_dict.get(node_b_id)

                if (
                    node_b
                    and len(node_b.dependencies) == 1
                    and node_b.dependencies[0] == node_a_id
                    and node_a.is_compatible_for_fusion_with(node_b)
                ):
                    # Eligible for fusion!
                    fused_id = f"{node_a.id}_{node_b.id}"
                    fused_name = f"{node_a.name} + {node_b.name}"
                    
                    # Fusing eliminates prompt framing and context duplication (~25% token savings)
                    combined_raw_tokens = node_a.estimated_tokens + node_b.estimated_tokens
                    fused_tokens = int(round(combined_raw_tokens * 0.78))
                    token_saved = combined_raw_tokens - fused_tokens

                    fused_node = WorkflowNode(
                        id=fused_id,
                        name=fused_name,
                        type=node_b.type,  # inherits final operation type
                        dependencies=list(node_a.dependencies),
                        required_quality=max(node_a.required_quality, node_b.required_quality),
                        priority=node_b.priority,
                        estimated_tokens=fused_tokens,
                        metadata={
                            "fused_from": [node_a.id, node_b.id],
                            "token_savings": token_saved,
                            **node_b.metadata,
                        },
                    )

                    # Update remaining nodes: children of node_b now depend on fused_node
                    new_nodes: List[WorkflowNode] = [fused_node]
                    for other in fused_wf.nodes:
                        if other.id in {node_a.id, node_b.id}:
                            continue
                        # Rewire dependencies
                        if node_b.id in other.dependencies:
                            new_deps = [
                                fused_id if dep == node_b.id else dep
                                for dep in other.dependencies
                            ]
                            new_nodes.append(other.model_copy(update={"dependencies": new_deps}))
                        else:
                            new_nodes.append(other)

                    fused_wf = Workflow(
                        id=fused_wf.id, name=fused_wf.name, nodes=new_nodes
                    )
                    combined_log.append(
                        {
                            "fused_node_id": fused_id,
                            "merged_nodes": [node_a.id, node_b.id],
                            "name": fused_name,
                            "token_savings": token_saved,
                        }
                    )
                    explanations.append(
                        f"Fused sequential steps '{node_a.name}' and '{node_b.name}' into combined operation '{fused_name}', eliminating intermediate context re-ingestion and saving {token_saved} tokens."
                    )
                    changed = True
                    break  # Break out to re-evaluate graph with new node list

    return fused_wf, combined_log, explanations


def optimize_workflow(
    workflow: Union[Workflow, Dict[str, Any]],
    constraints: Optional[Union[OptimizationConstraints, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Optimizes an AI workflow DAG as a whole and returns structured comparative metrics.

    Args:
        workflow: A Workflow instance or a dictionary representing the workflow DAG.
        constraints: Optional OptimizationConstraints instance or dictionary.

    Returns:
        Structured dictionary matching OptimizationResult schema.
    """
    # 1. Normalize Workflow input
    if isinstance(workflow, dict):
        wf = Workflow.model_validate(workflow)
    elif isinstance(workflow, Workflow):
        wf = workflow.clone()
    else:
        raise ValueError(f"Invalid workflow input type: {type(workflow)}")

    # 2. Normalize Constraints input
    if constraints is None:
        c = OptimizationConstraints()
    elif isinstance(constraints, dict):
        c = OptimizationConstraints.model_validate(constraints)
    elif isinstance(constraints, OptimizationConstraints):
        c = constraints
    else:
        raise ValueError(f"Invalid constraints input type: {type(constraints)}")

    # 3. Validate Baseline DAG
    baseline_dag = WorkflowDAG(wf)
    baseline_dag.detect_cycles()

    # Baseline assumes standard default execution (sequential dispatch, unoptimized)
    baseline_metrics = compute_workflow_metrics(baseline_dag, is_parallel=False)

    explanations: List[str] = []
    removed_nodes: List[Dict[str, Any]] = []
    combined_nodes: List[Dict[str, Any]] = []

    current_wf = wf

    # 4. Pass 1: Pruning redundant & duplicate nodes
    if c.enable_pruning:
        pruned_wf, prune_log, prune_exps = _prune_redundant_nodes(WorkflowDAG(current_wf))
        removed_nodes.extend(prune_log)
        explanations.extend(prune_exps)
        current_wf = pruned_wf

    # 5. Pass 2: Fusing compatible linear steps
    if c.enable_fusion:
        fused_wf, fuse_log, fuse_exps = _fuse_linear_steps(WorkflowDAG(current_wf))
        combined_nodes.extend(fuse_log)
        explanations.extend(fuse_exps)
        current_wf = fused_wf

    # 6. Analyze Optimized DAG Topology & Concurrency
    optimized_dag = WorkflowDAG(current_wf)
    parallel_stages = optimized_dag.get_parallel_stages()
    parallel_groups = optimized_dag.get_parallel_groups()

    for group in parallel_groups:
        node_names = [optimized_dag.nodes_by_id[nid].name for nid in group]
        explanations.append(
            f"Scheduled parallel execution for independent steps: {', '.join(node_names)}."
        )

    # 7. Compute Optimized Metrics (with parallel critical-path execution)
    optimized_metrics = compute_workflow_metrics(optimized_dag, is_parallel=True)

    # 8. Check Constraints Feasibility
    if c.carbon_budget is not None:
        if optimized_metrics.estimated_carbon_g_co2 > c.carbon_budget:
            explanations.append(
                f"WARNING: Optimized carbon ({optimized_metrics.estimated_carbon_g_co2:.2f}g) exceeds carbon budget ({c.carbon_budget:.2f}g). Downstream scheduler must downgrade models or shift region."
            )
        else:
            explanations.append(
                f"Carbon budget constraint satisfied: {optimized_metrics.estimated_carbon_g_co2:.2f}g <= {c.carbon_budget:.2f}g."
            )

    if c.deadline is not None:
        if optimized_metrics.critical_path_latency_sec > c.deadline:
            explanations.append(
                f"WARNING: Critical path latency ({optimized_metrics.critical_path_latency_sec:.2f}s) exceeds deadline ({c.deadline:.2f}s)."
            )
        else:
            slack = round(c.deadline - optimized_metrics.critical_path_latency_sec, 2)
            explanations.append(
                f"Deadline constraint satisfied: completion in {optimized_metrics.critical_path_latency_sec:.2f}s with {slack}s of deadline slack."
            )

    # 9. Compute Improvement Percentages
    def calc_pct_reduction(base_val: float, opt_val: float) -> float:
        if base_val <= 0.0:
            return 0.0
        return round(max(0.0, ((base_val - opt_val) / base_val) * 100.0), 2)

    improvement = OptimizationImprovement(
        latency_reduction_pct=calc_pct_reduction(
            baseline_metrics.sequential_latency_sec,
            optimized_metrics.critical_path_latency_sec,
        ),
        carbon_reduction_pct=calc_pct_reduction(
            baseline_metrics.estimated_carbon_g_co2,
            optimized_metrics.estimated_carbon_g_co2,
        ),
        cost_reduction_pct=calc_pct_reduction(
            baseline_metrics.estimated_cost_usd,
            optimized_metrics.estimated_cost_usd,
        ),
        token_reduction_pct=calc_pct_reduction(
            baseline_metrics.total_tokens,
            optimized_metrics.total_tokens,
        ),
        baseline_metrics=baseline_metrics,
        optimized_metrics=optimized_metrics,
    )

    result = OptimizationResult(
        baseline_workflow=wf.model_dump(),
        optimized_workflow=current_wf.model_dump(),
        baseline_node_count=len(wf.nodes),
        optimized_node_count=len(current_wf.nodes),
        parallel_groups=parallel_groups,
        removed_nodes=removed_nodes,
        combined_nodes=combined_nodes,
        estimated_improvement=improvement,
        explanations=explanations,
    )

    return result.model_dump()

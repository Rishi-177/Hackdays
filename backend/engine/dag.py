"""DAG engine for CarbonPilot.

Provides graph analysis, cycle detection, topological sorting,
parallel execution stage grouping, critical path computation, and helper DAG validation functions.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Set, Tuple, Union

from backend.models.workflow import Workflow, WorkflowNode


class DAGValidationError(Exception):
    """Raised when the workflow graph contains invalid references or malformed structures."""
    pass


class CycleError(Exception):
    """Raised when a circular dependency / cycle is detected in the workflow graph."""
    pass


class WorkflowDAG:
    """Manages graph topology, validation, and parallel execution scheduling analysis."""

    def __init__(self, workflow: Workflow) -> None:
        self.workflow = workflow
        self.nodes_by_id: Dict[str, WorkflowNode] = {
            node.id: node for node in workflow.nodes
        }
        self.adj: Dict[str, Set[str]] = defaultdict(set)       # parent -> children (successors)
        self.pred: Dict[str, Set[str]] = defaultdict(set)      # child -> parents (predecessors)
        self.in_degree: Dict[str, int] = defaultdict(int)

        self._build_and_validate()

    def _build_and_validate(self) -> None:
        """Constructs graph adjacency and validates nodes and references."""
        # 1. Check duplicate IDs
        seen_ids: Set[str] = set()
        for node in self.workflow.nodes:
            if node.id in seen_ids:
                raise DAGValidationError(f"Duplicate node ID detected: '{node.id}'")
            seen_ids.add(node.id)

        # 2. Check dependency existence and populate adjacency
        for node in self.workflow.nodes:
            if node.id not in self.in_degree:
                self.in_degree[node.id] = 0

            for dep_id in node.dependencies:
                if dep_id not in self.nodes_by_id:
                    raise DAGValidationError(
                        f"Node '{node.id}' references non-existent dependency '{dep_id}'"
                    )
                if dep_id == node.id:
                    raise CycleError(f"Self-dependency detected in node '{node.id}'")

                self.adj[dep_id].add(node.id)
                self.pred[node.id].add(dep_id)
                self.in_degree[node.id] += 1

    def detect_cycles(self) -> None:
        """Checks for cycles in the graph using DFS. Raises CycleError if found."""
        visited: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
        cycle_path: List[str] = []

        def dfs(node_id: str) -> bool:
            visited[node_id] = 1
            cycle_path.append(node_id)

            for neighbor in sorted(self.adj[node_id]):
                if visited.get(neighbor, 0) == 1:
                    cycle_start_idx = cycle_path.index(neighbor)
                    cycle_loop = cycle_path[cycle_start_idx:] + [neighbor]
                    raise CycleError(
                        f"Cycle detected in workflow: {' -> '.join(cycle_loop)}"
                    )
                if visited.get(neighbor, 0) == 0:
                    if dfs(neighbor):
                        return True

            cycle_path.pop()
            visited[node_id] = 2
            return False

        for node_id in sorted(self.nodes_by_id.keys()):
            if visited.get(node_id, 0) == 0:
                dfs(node_id)

    def get_topological_order(self) -> List[str]:
        """Returns nodes in topological order using Kahn's algorithm with deterministic tie-breaking.

        Raises CycleError if graph contains a cycle.
        """
        self.detect_cycles()

        in_deg = dict(self.in_degree)
        zero_in = [nid for nid, deg in in_deg.items() if deg == 0]
        zero_in.sort()
        queue = deque(zero_in)

        ordered: List[str] = []
        while queue:
            current = queue.popleft()
            ordered.append(current)

            for succ in sorted(self.adj[current]):
                in_deg[succ] -= 1
                if in_deg[succ] == 0:
                    queue.append(succ)
            queue = deque(sorted(queue))

        if len(ordered) != len(self.nodes_by_id):
            raise CycleError("Unresolvable dependencies detected in workflow (cycle present).")

        return ordered

    def get_root_nodes(self) -> List[str]:
        """Returns nodes with no dependencies (entry points of the workflow)."""
        roots = [nid for nid, node in self.nodes_by_id.items() if not node.dependencies]
        return sorted(roots)

    def get_leaf_nodes(self) -> List[str]:
        """Returns terminal nodes with no outgoing dependencies."""
        leaves = [nid for nid in self.nodes_by_id.keys() if not self.adj[nid]]
        return sorted(leaves)

    def get_ancestors(self, node_id: str) -> Set[str]:
        """Returns all transitive ancestors (predecessors) of a node."""
        ancestors: Set[str] = set()
        queue = deque(self.pred[node_id])
        while queue:
            curr = queue.popleft()
            if curr not in ancestors:
                ancestors.add(curr)
                queue.extend(self.pred[curr])
        return ancestors

    def get_descendants(self, node_id: str) -> Set[str]:
        """Returns all transitive descendants (successors) of a node."""
        descendants: Set[str] = set()
        queue = deque(self.adj[node_id])
        while queue:
            curr = queue.popleft()
            if curr not in descendants:
                descendants.add(curr)
                queue.extend(self.adj[curr])
        return descendants

    def are_independent(self, node_a: str, node_b: str) -> bool:
        """Determines if two nodes are causally independent (neither depends on the other)."""
        if node_a == node_b:
            return False
        a_desc = self.get_descendants(node_a)
        if node_b in a_desc:
            return False
        b_desc = self.get_descendants(node_b)
        return node_a not in b_desc

    def get_parallel_stages(self) -> List[List[str]]:
        """Partitions the workflow into topological execution stages (levels)."""
        top_order = self.get_topological_order()
        levels: Dict[str, int] = {}

        for nid in top_order:
            parents = self.pred[nid]
            if not parents:
                levels[nid] = 0
            else:
                levels[nid] = max(levels[p] for p in parents) + 1

        stage_map: Dict[int, List[str]] = defaultdict(list)
        for nid, lvl in levels.items():
            stage_map[lvl].append(nid)

        stages: List[List[str]] = []
        for lvl in sorted(stage_map.keys()):
            stages.append(sorted(stage_map[lvl]))

        return stages

    def get_parallel_groups(self) -> List[List[str]]:
        """Returns all multi-node groups in the workflow that can run concurrently."""
        stages = self.get_parallel_stages()
        return [stage for stage in stages if len(stage) > 1]

    def compute_critical_path(self, latency_fn=None) -> Tuple[List[str], float]:
        """Computes the critical path (longest dependency chain in seconds)."""
        top_order = self.get_topological_order()
        if not top_order:
            return [], 0.0

        if latency_fn is None:
            def default_latency(node: WorkflowNode) -> float:
                return round(1.0 + (node.estimated_tokens / 1000.0) * 1.2, 2)
            latency_fn = default_latency

        dist: Dict[str, float] = {}
        prev: Dict[str, str | None] = {}

        for nid in top_order:
            node = self.nodes_by_id[nid]
            node_lat = latency_fn(node)

            parents = self.pred[nid]
            if not parents:
                dist[nid] = node_lat
                prev[nid] = None
            else:
                max_parent = max(parents, key=lambda p: dist[p])
                dist[nid] = round(dist[max_parent] + node_lat, 2)
                prev[nid] = max_parent

        end_node = max(dist.keys(), key=lambda n: dist[n])
        total_latency = dist[end_node]

        path: List[str] = []
        curr: str | None = end_node
        while curr is not None:
            path.append(curr)
            curr = prev.get(curr)

        path.reverse()
        return path, total_latency


# Dev 2 Helper Functions for API layer compatibility
def validate_dag(dag: Dict[str, Any]) -> bool:
    """Validates that a workflow DAG contains valid nodes and edges without cycles."""
    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    node_ids = {node["node_id"] if isinstance(node, dict) and "node_id" in node else str(node) for node in nodes}

    for edge in edges:
        source = edge.get("source") if isinstance(edge, dict) else edge[0]
        target = edge.get("target") if isinstance(edge, dict) else edge[1]
        if source not in node_ids or target not in node_ids:
            return False

    in_degree = {nid: 0 for nid in node_ids}
    adj = {nid: [] for nid in node_ids}

    for edge in edges:
        source = edge.get("source") if isinstance(edge, dict) else edge[0]
        target = edge.get("target") if isinstance(edge, dict) else edge[1]
        adj[source].append(target)
        in_degree[target] += 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    visited_count = 0

    while queue:
        curr = queue.pop(0)
        visited_count += 1
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return visited_count == len(node_ids)


def get_critical_path_depth(dag: Dict[str, Any]) -> int:
    """Calculates the max length (depth) of dependent nodes in the DAG."""
    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])
    node_ids = [node["node_id"] if isinstance(node, dict) and "node_id" in node else str(node) for node in nodes]

    adj = {nid: [] for nid in node_ids}
    in_degree = {nid: 0 for nid in node_ids}

    for edge in edges:
        source = edge.get("source") if isinstance(edge, dict) else edge[0]
        target = edge.get("target") if isinstance(edge, dict) else edge[1]
        if source in adj and target in adj:
            adj[source].append(target)
            in_degree[target] += 1

    depths = {nid: 1 for nid in node_ids}
    queue = [nid for nid, deg in in_degree.items() if deg == 0]

    while queue:
        curr = queue.pop(0)
        for neighbor in adj[curr]:
            depths[neighbor] = max(depths[neighbor], depths[curr] + 1)
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return max(depths.values()) if depths else 1

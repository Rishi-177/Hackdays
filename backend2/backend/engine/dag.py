"""
DAG Validation and Dependency Analysis Module for CarbonPilot.
"""

from typing import Any, Dict, List, Set


def validate_dag(dag: Dict[str, Any]) -> bool:
    """
    Validates that a workflow DAG contains valid nodes and edges without cycles.
    """
    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    node_ids = {node["node_id"] if isinstance(node, dict) and "node_id" in node else str(node) for node in nodes}

    # Check edge references
    for edge in edges:
        source = edge.get("source") if isinstance(edge, dict) else edge[0]
        target = edge.get("target") if isinstance(edge, dict) else edge[1]
        if source not in node_ids or target not in node_ids:
            return False

    # Check for cycles using Kahn's algorithm
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

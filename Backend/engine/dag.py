"""
CarbonPilot DAG Engine

DAG structure validation, dependency checking, and topological ordering.
"""

from typing import Any, Dict, List, Set


def validate_dag(nodes: List[Dict[str, Any]]) -> bool:
    """Checks if the given node list forms a valid Directed Acyclic Graph (DAG)."""
    node_ids: Set[str] = {str(n.get("node_id", n.get("id"))) for n in nodes}

    # Verify all dependencies exist in node_ids
    for node in nodes:
        deps = node.get("dependencies", [])
        for d in deps:
            if d not in node_ids:
                return False

    # Check for cycles using Kahn's algorithm
    try:
        topological_sort(nodes)
        return True
    except ValueError:
        return False


def topological_sort(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Returns nodes sorted in topological dependency execution order."""
    node_map = {str(n.get("node_id", n.get("id"))): dict(n) for n in nodes}
    in_degree = {nid: 0 for nid in node_map}
    adj_list = {nid: [] for nid in node_map}

    for nid, ndata in node_map.items():
        deps = ndata.get("dependencies", [])
        for d in deps:
            if d in adj_list:
                adj_list[d].append(nid)
                in_degree[nid] += 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    sorted_order = []

    while queue:
        curr = queue.pop(0)
        sorted_order.append(node_map[curr])
        for neighbor in adj_list[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_order) != len(nodes):
        raise ValueError("Cycle detected in DAG definition")

    return sorted_order

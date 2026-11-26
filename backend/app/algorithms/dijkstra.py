"""
Educational Dijkstra Shortest-Path Module.

NOTE: This module is strictly for educational demonstration of graph-based
shortest-path routing on small road networks. Production road routing in
SmartNav AI uses OSRM (Open Source Routing Machine) via app/services/routing.py.
"""

import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    lat: float
    lng: float


@dataclass(frozen=True)
class GraphEdge:
    to_node: str
    weight_meters: float


def dijkstra_shortest_path(
    nodes: Dict[str, GraphNode],
    adjacency: Dict[str, List[GraphEdge]],
    start_id: str,
    goal_id: str,
) -> Tuple[Optional[List[str]], float]:
    """
    Compute the shortest path between start_id and goal_id using Dijkstra's algorithm.
    Returns (path_node_ids, total_distance_meters) or (None, inf) if unreachable.
    """
    if start_id not in nodes or goal_id not in nodes:
        raise ValueError("Start or goal node does not exist in the graph.")

    distances: Dict[str, float] = {node_id: float("inf") for node_id in nodes}
    previous: Dict[str, Optional[str]] = {node_id: None for node_id in nodes}
    distances[start_id] = 0.0

    heap: List[Tuple[float, str]] = [(0.0, start_id)]
    visited = set()

    while heap:
        current_dist, current_id = heapq.heappop(heap)
        if current_id in visited:
            continue
        visited.add(current_id)

        if current_id == goal_id:
            break

        for edge in adjacency.get(current_id, []):
            if edge.weight_meters < 0:
                raise ValueError("Dijkstra requires non-negative edge weights.")
            candidate = current_dist + edge.weight_meters
            if candidate < distances[edge.to_node]:
                distances[edge.to_node] = candidate
                previous[edge.to_node] = current_id
                heapq.heappush(heap, (candidate, edge.to_node))

    if distances[goal_id] == float("inf"):
        return None, float("inf")

    path: List[str] = []
    cursor: Optional[str] = goal_id
    while cursor is not None:
        path.append(cursor)
        cursor = previous[cursor]
    path.reverse()
    return path, distances[goal_id]

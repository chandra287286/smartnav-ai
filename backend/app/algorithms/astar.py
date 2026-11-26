"""
Educational A* (A-Star) Shortest-Path Module.

NOTE: This module is strictly for educational demonstration of heuristic
graph search using great-circle (Haversine) admissible lower-bound heuristics.
Production road routing in SmartNav AI uses OSRM via app/services/routing.py.
"""

import heapq
import math
from typing import Dict, List, Optional, Tuple

from app.algorithms.dijkstra import GraphEdge, GraphNode

EARTH_RADIUS_METERS = 6371000.0


def haversine_meters(a: GraphNode, b: GraphNode) -> float:
    lat1, lng1 = math.radians(a.lat), math.radians(a.lng)
    lat2, lng2 = math.radians(b.lat), math.radians(b.lng)
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def astar_shortest_path(
    nodes: Dict[str, GraphNode],
    adjacency: Dict[str, List[GraphEdge]],
    start_id: str,
    goal_id: str,
) -> Tuple[Optional[List[str]], float]:
    """
    Compute the shortest path between start_id and goal_id using A* with a
    Haversine Euclidean-on-sphere admissible heuristic.
    """
    if start_id not in nodes or goal_id not in nodes:
        raise ValueError("Start or goal node does not exist in the graph.")

    goal_node = nodes[goal_id]
    g_score: Dict[str, float] = {node_id: float("inf") for node_id in nodes}
    f_score: Dict[str, float] = {node_id: float("inf") for node_id in nodes}
    came_from: Dict[str, Optional[str]] = {node_id: None for node_id in nodes}

    g_score[start_id] = 0.0
    f_score[start_id] = haversine_meters(nodes[start_id], goal_node)

    open_heap: List[Tuple[float, str]] = [(f_score[start_id], start_id)]
    closed_set = set()

    while open_heap:
        _, current_id = heapq.heappop(open_heap)
        if current_id in closed_set:
            continue
        if current_id == goal_id:
            path: List[str] = []
            cursor: Optional[str] = goal_id
            while cursor is not None:
                path.append(cursor)
                cursor = came_from[cursor]
            path.reverse()
            return path, g_score[goal_id]

        closed_set.add(current_id)

        for edge in adjacency.get(current_id, []):
            if edge.weight_meters < 0:
                raise ValueError("A* requires non-negative edge weights.")
            tentative_g = g_score[current_id] + edge.weight_meters
            if tentative_g < g_score[edge.to_node]:
                came_from[edge.to_node] = current_id
                g_score[edge.to_node] = tentative_g
                f_score[edge.to_node] = tentative_g + haversine_meters(nodes[edge.to_node], goal_node)
                heapq.heappush(open_heap, (f_score[edge.to_node], edge.to_node))

    return None, float("inf")

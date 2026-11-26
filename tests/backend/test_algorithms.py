import pytest

from app.algorithms.astar import astar_shortest_path
from app.algorithms.dijkstra import GraphEdge, GraphNode, dijkstra_shortest_path


def _sample_road_graph():
    nodes = {
        "A": GraphNode("A", 37.7749, -122.4194),
        "B": GraphNode("B", 37.7780, -122.4194),
        "C": GraphNode("C", 37.7780, -122.4100),
        "D": GraphNode("D", 37.7849, -122.4094),
        "Z": GraphNode("Z", 37.8000, -122.4000),  # Disconnected
    }
    adjacency = {
        "A": [GraphEdge("B", 350.0), GraphEdge("C", 1200.0)],
        "B": [GraphEdge("C", 820.0), GraphEdge("D", 1400.0)],
        "C": [GraphEdge("D", 770.0)],
        "D": [],
        "Z": [],
    }
    return nodes, adjacency


def test_dijkstra_and_astar_agree_on_shortest_path():
    nodes, adj = _sample_road_graph()
    d_path, d_cost = dijkstra_shortest_path(nodes, adj, "A", "D")
    a_path, a_cost = astar_shortest_path(nodes, adj, "A", "D")

    assert d_path == ["A", "B", "D"]
    assert d_cost == pytest.approx(1750.0)
    assert a_path == d_path
    assert a_cost == pytest.approx(d_cost)


def test_unreachable_node_returns_none_and_inf():
    nodes, adj = _sample_road_graph()
    path, cost = dijkstra_shortest_path(nodes, adj, "A", "Z")
    assert path is None
    assert cost == float("inf")

    a_path, a_cost = astar_shortest_path(nodes, adj, "A", "Z")
    assert a_path is None
    assert a_cost == float("inf")

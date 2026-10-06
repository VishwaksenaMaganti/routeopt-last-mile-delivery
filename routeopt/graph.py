"""Weighted undirected graphs and shortest-path / spanning-tree algorithms."""

from __future__ import annotations

from heapq import heappop, heappush
from math import inf, isfinite
from typing import Iterable, Mapping, Sequence

Edge = tuple[str, str, float]
Adjacency = dict[str, list[tuple[str, float]]]


def build_adjacency(nodes: Iterable[str], edges: Iterable[Edge]) -> Adjacency:
    """Build a sorted adjacency list from an undirected weighted road network."""
    adjacency: Adjacency = {str(node): [] for node in nodes}
    for first, second, distance in edges:
        first, second, distance = str(first), str(second), float(distance)
        if first not in adjacency or second not in adjacency:
            raise ValueError(f"Road endpoint is not a known node: {first} - {second}")
        if first == second:
            raise ValueError(f"Self-loop roads are not supported: {first}")
        if not isfinite(distance) or distance <= 0:
            raise ValueError("Road distances must be greater than zero.")
        adjacency[first].append((second, distance))
        adjacency[second].append((first, distance))
    for neighbours in adjacency.values():
        neighbours.sort(key=lambda pair: pair[0])
    return adjacency


def dijkstra(adjacency: Mapping[str, Sequence[tuple[str, float]]], source: str):
    """Return single-source distances and predecessor pointers using a min-heap."""
    if source not in adjacency:
        raise ValueError(f"Unknown source node: {source}")
    distances = {node: inf for node in adjacency}
    previous: dict[str, str | None] = {node: None for node in adjacency}
    distances[source] = 0.0
    queue: list[tuple[float, str]] = [(0.0, source)]
    while queue:
        distance, node = heappop(queue)
        if distance != distances[node]:
            continue
        for neighbour, weight in adjacency[node]:
            candidate = distance + weight
            if candidate < distances[neighbour]:
                distances[neighbour] = candidate
                previous[neighbour] = node
                heappush(queue, (candidate, neighbour))
    return distances, previous


def reconstruct_path(previous: Mapping[str, str | None], source: str, target: str) -> list[str]:
    """Reconstruct a path returned by :func:`dijkstra`, or return [] if unreachable."""
    if source == target:
        return [source]
    path: list[str] = []
    node: str | None = target
    while node is not None:
        path.append(node)
        if node == source:
            return list(reversed(path))
        node = previous.get(node)
    return []


def floyd_warshall(adjacency: Mapping[str, Sequence[tuple[str, float]]]):
    """Return all-pairs distances and next-hop pointers in O(V^3) time."""
    nodes = list(adjacency)
    distances = {source: {target: (0.0 if source == target else inf) for target in nodes}
                 for source in nodes}
    next_hop: dict[str, dict[str, str | None]] = {
        source: {target: (target if source == target else None) for target in nodes}
        for source in nodes
    }
    for source, neighbours in adjacency.items():
        for target, weight in neighbours:
            if weight < distances[source][target]:
                distances[source][target] = weight
                next_hop[source][target] = target
    for intermediate in nodes:
        for source in nodes:
            if distances[source][intermediate] == inf:
                continue
            for target in nodes:
                candidate = distances[source][intermediate] + distances[intermediate][target]
                if candidate < distances[source][target]:
                    distances[source][target] = candidate
                    next_hop[source][target] = next_hop[source][intermediate]
    return distances, next_hop


def floyd_path(next_hop: Mapping[str, Mapping[str, str | None]], source: str, target: str) -> list[str]:
    """Reconstruct a Floyd-Warshall path from its next-hop matrix."""
    if source not in next_hop or target not in next_hop[source]:
        return []
    if source == target:
        return [source]
    if next_hop[source][target] is None:
        return []
    path = [source]
    current = source
    for _ in range(len(next_hop) + 1):
        current = next_hop[current][target]  # type: ignore[assignment]
        if current is None:
            return []
        path.append(current)
        if current == target:
            return path
    raise RuntimeError("Floyd-Warshall next-hop matrix contains a cycle.")


def kruskal(nodes: Iterable[str], edges: Iterable[Edge]):
    """Return a minimum spanning forest using Kruskal's greedy algorithm."""
    ordered_nodes = sorted({str(node) for node in nodes})
    parent = {node: node for node in ordered_nodes}
    rank = {node: 0 for node in ordered_nodes}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    forest: list[Edge] = []
    total = 0.0
    for first, second, distance in sorted(edges, key=lambda edge: (float(edge[2]), str(edge[0]), str(edge[1]))):
        first, second, distance = str(first), str(second), float(distance)
        if first not in parent or second not in parent or first == second:
            continue
        root_a, root_b = find(first), find(second)
        if root_a == root_b:
            continue
        if rank[root_a] < rank[root_b]:
            root_a, root_b = root_b, root_a
        parent[root_b] = root_a
        if rank[root_a] == rank[root_b]:
            rank[root_a] += 1
        forest.append((first, second, distance))
        total += distance
    components = len({find(node) for node in ordered_nodes})
    return forest, total, components


def prim(nodes: Iterable[str], edges: Iterable[Edge]):
    """Return a minimum spanning forest using Prim's greedy algorithm."""
    ordered_nodes = sorted({str(node) for node in nodes})
    adjacency: Adjacency = {node: [] for node in ordered_nodes}
    for first, second, distance in edges:
        first, second, distance = str(first), str(second), float(distance)
        if first in adjacency and second in adjacency and first != second:
            adjacency[first].append((second, distance))
            adjacency[second].append((first, distance))
    forest: list[Edge] = []
    visited: set[str] = set()
    total = 0.0
    components = 0
    for root in ordered_nodes:
        if root in visited:
            continue
        components += 1
        visited.add(root)
        queue: list[tuple[float, str, str]] = []
        for neighbour, weight in adjacency[root]:
            heappush(queue, (weight, root, neighbour))
        while queue:
            weight, first, second = heappop(queue)
            if second in visited:
                continue
            visited.add(second)
            forest.append((first, second, weight))
            total += weight
            for neighbour, next_weight in adjacency[second]:
                if neighbour not in visited:
                    heappush(queue, (next_weight, second, neighbour))
    return forest, total, components

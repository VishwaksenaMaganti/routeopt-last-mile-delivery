"""Responsive SVG views for the road graph, delivery route, and MST overlay."""

from __future__ import annotations

import math
from html import escape
from typing import Iterable, Mapping, Sequence


def graph_figure(
    nodes: Sequence[Mapping],
    edges: Sequence[Mapping],
    route_nodes: Sequence[str] | None = None,
    tree_edges: Iterable[tuple[str, str, float]] | None = None,
) -> str:
    """Return an accessible inline SVG with optional route/tree highlights."""
    ordered = sorted((dict(node) for node in nodes), key=lambda row: (row.get("node") != "W", str(row.get("node"))))
    count = max(1, len(ordered))
    center_x, center_y, radius_x, radius_y = 450.0, 245.0, 255.0, 150.0
    positions = {
        str(node["node"]): (
            center_x + radius_x * math.cos(-math.pi / 2 + 2 * math.pi * index / count),
            center_y + radius_y * math.sin(-math.pi / 2 + 2 * math.pi * index / count),
        )
        for index, node in enumerate(ordered)
    }
    sequence = list(route_nodes or [])
    route_set = {tuple(sorted((str(first), str(second)))) for first, second in zip(sequence, sequence[1:])}
    tree_set = {tuple(sorted((str(first), str(second)))) for first, second, _ in (tree_edges or [])}
    bits = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 520" role="img" '
        'aria-labelledby="routeopt-graph-title" style="display:block;width:100%;height:auto;background:#ffffff">',
        '<title id="routeopt-graph-title">Road network with distance labels and selected overlays</title>',
        '<rect x="0" y="0" width="900" height="520" fill="#ffffff"/>',
    ]

    def line(first: str, second: str, stroke: str, width: int) -> str:
        x1, y1 = positions[first]
        x2, y2 = positions[second]
        title = escape(f"{first} to {second}")
        return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{stroke}" stroke-width="{width}" stroke-linecap="round"><title>{title}</title></line>')

    for edge in edges:
        first, second = str(edge["from"]), str(edge["to"])
        if first not in positions or second not in positions:
            continue
        x1, y1 = positions[first]
        x2, y2 = positions[second]
        distance = float(edge["distance_km"])
        key = tuple(sorted((first, second)))
        bits.append(line(first, second, "#cbd5e1", 3))
        if key in tree_set:
            bits.append(line(first, second, "#d99b27", 6))
        if key in route_set:
            bits.append(line(first, second, "#0f766e", 7))
        midpoint_x, midpoint_y = (x1 + x2) / 2, (y1 + y2) / 2
        delta_x, delta_y = x2 - x1, y2 - y1
        length = max(math.hypot(delta_x, delta_y), 1.0)
        label_x = midpoint_x - delta_y / length * 12
        label_y = midpoint_y + delta_x / length * 12
        bits.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="13" fill="#475569" '
            'paint-order="stroke" stroke="#ffffff" stroke-width="5" stroke-linejoin="round">'
            f'{distance:g} km</text>'
        )

    for node in ordered:
        node_id = str(node["node"])
        label = str(node.get("label", node_id))
        kind = str(node.get("kind", "Waypoint"))
        x, y = positions[node_id]
        fill = "#d99b27" if kind == "Warehouse" else "#0f766e" if kind == "Pickup" else "#344b56"
        bits.append(
            f'<g><title>{escape(label)} ({escape(node_id)}) - {escape(kind)}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="22" fill="{fill}" stroke="#ffffff" stroke-width="3"/>'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-weight="700" font-size="13" fill="#ffffff">{escape(node_id)}</text>'
            f'<text x="{x:.1f}" y="{y + 42:.1f}" text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-size="12" fill="#263238">{escape(label)}</text></g>'
        )
    bits.append(
        '<g font-family="Arial, sans-serif" font-size="12" fill="#475569">'
        '<circle cx="32" cy="484" r="8" fill="#d99b27"/><text x="46" y="488">Warehouse</text>'
        '<circle cx="151" cy="484" r="8" fill="#0f766e"/><text x="165" y="488">Pickup</text>'
        '<circle cx="241" cy="484" r="8" fill="#344b56"/><text x="255" y="488">Delivery / other</text>'
        '<line x1="393" y1="484" x2="421" y2="484" stroke="#0f766e" stroke-width="6"/><text x="429" y="488">Route</text>'
        '<line x1="495" y1="484" x2="523" y2="484" stroke="#d99b27" stroke-width="6"/><text x="531" y="488">MST backbone</text>'
        '</g></svg>'
    )
    return "".join(bits)

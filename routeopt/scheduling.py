"""Deadline-aware greedy ordering heuristic and final route construction."""

from __future__ import annotations

from math import isfinite
from typing import Mapping, Sequence

from .graph import floyd_path


def _path_distance(path: Sequence[str], distances: Mapping[str, Mapping[str, float]]) -> float:
    if len(path) < 2:
        return 0.0
    return sum(float(distances[a][b]) for a, b in zip(path, path[1:]))


def greedy_delivery_route(
    selected_orders: Sequence[Mapping],
    start: str,
    distances: Mapping[str, Mapping[str, float]],
    next_hop: Mapping[str, Mapping[str, str | None]],
    speed_kmh: float,
    return_to_start: bool = False,
):
    """Create a route with a transparent greedy score, not a global optimum.

    Each iteration ranks feasible next orders with weighted factors:
    deadline urgency (0.45), profit per estimated delivery hour (0.35), and
    travel efficiency (0.20). Deadlines are hours after departure.
    """
    if not isfinite(speed_kmh) or speed_kmh <= 0:
        raise ValueError("Vehicle speed must be greater than zero.")
    current = start
    elapsed_minutes = 0.0
    total_distance = 0.0
    route_nodes = [start]
    remaining = [dict(order) for order in selected_orders]
    stops: list[dict] = []
    legs: list[dict] = []
    skipped: list[dict] = []

    while remaining:
        candidates: list[dict] = []
        for order in remaining:
            pickup = str(order["pickup"])
            drop = str(order["drop"])
            to_pickup = floyd_path(next_hop, current, pickup)
            pickup_to_drop = floyd_path(next_hop, pickup, drop)
            if not to_pickup or not pickup_to_drop:
                continue
            approach_km = _path_distance(to_pickup, distances)
            delivery_km = _path_distance(pickup_to_drop, distances)
            travel_minutes = (approach_km + delivery_km) / speed_kmh * 60.0
            service_minutes = max(0.0, float(order.get("service_minutes", 0.0)))
            delivery_minutes = max(travel_minutes + service_minutes, 0.1)
            projected_drop = elapsed_minutes + (approach_km + delivery_km) / speed_kmh * 60.0
            deadline_minutes = float(order["deadline_hr"]) * 60.0
            slack_minutes = deadline_minutes - projected_drop
            urgency = 1.0 / (1.0 + max(slack_minutes, 0.0) / 60.0)
            if slack_minutes < 0:
                urgency += min(1.0, abs(slack_minutes) / max(deadline_minutes, 60.0))
            candidates.append({
                "order": order,
                "to_pickup": to_pickup,
                "pickup_to_drop": pickup_to_drop,
                "approach_km": approach_km,
                "delivery_km": delivery_km,
                "travel_minutes": travel_minutes,
                "service_minutes": service_minutes,
                "delivery_minutes": delivery_minutes,
                "projected_drop_minutes": projected_drop,
                "slack_minutes": slack_minutes,
                "urgency": urgency,
                "profit_rate": float(order["profit"]) / delivery_minutes,
                "travel_efficiency": 1.0 / delivery_minutes,
            })
        if not candidates:
            skipped.extend(remaining)
            break

        max_profit_rate = max(item["profit_rate"] for item in candidates) or 1.0
        max_travel_efficiency = max(item["travel_efficiency"] for item in candidates) or 1.0
        for item in candidates:
            item["profit_factor"] = item["profit_rate"] / max_profit_rate
            item["travel_factor"] = item["travel_efficiency"] / max_travel_efficiency
            item["priority_score"] = (
                0.45 * item["urgency"]
                + 0.35 * item["profit_factor"]
                + 0.20 * item["travel_factor"]
            )
        chosen = max(
            candidates,
            key=lambda item: (
                item["priority_score"],
                -float(item["order"]["deadline_hr"]),
                float(item["order"]["profit"]),
                str(item["order"]["order_id"]),
            ),
        )
        order = chosen["order"]
        start_minute = elapsed_minutes
        leg_origin = current
        if len(chosen["to_pickup"]) > 1:
            route_nodes.extend(chosen["to_pickup"][1:])
        if len(chosen["pickup_to_drop"]) > 1:
            route_nodes.extend(chosen["pickup_to_drop"][1:])
        approach_km = chosen["approach_km"]
        delivery_km = chosen["delivery_km"]
        leg_km = approach_km + delivery_km
        total_distance += leg_km
        pickup_arrival = start_minute + approach_km / speed_kmh * 60.0
        drop_arrival = start_minute + (approach_km + delivery_km) / speed_kmh * 60.0
        elapsed_minutes = drop_arrival + chosen["service_minutes"]
        current = str(order["drop"])
        deadline_minutes = float(order["deadline_hr"]) * 60.0
        on_time = drop_arrival <= deadline_minutes
        stops.append({
            "order_id": str(order["order_id"]),
            "pickup": str(order["pickup"]),
            "drop": str(order["drop"]),
            "pickup_arrival_min": pickup_arrival,
            "drop_arrival_min": drop_arrival,
            "deadline_min": deadline_minutes,
            "slack_min": deadline_minutes - drop_arrival,
            "on_time": on_time,
            "profit": float(order["profit"]),
            "weight_kg": float(order["weight_kg"]),
            "priority_score": float(chosen["priority_score"]),
        })
        legs.append({
            "order_id": str(order["order_id"]),
            "from": leg_origin,
            "pickup": str(order["pickup"]),
            "drop": str(order["drop"]),
            "distance_km": leg_km,
            "travel_minutes": chosen["travel_minutes"],
            "path_to_pickup": chosen["to_pickup"],
            "path_to_drop": chosen["pickup_to_drop"],
        })
        remaining.remove(order)

    return_distance = 0.0
    if return_to_start and current != start:
        return_path = floyd_path(next_hop, current, start)
        if return_path:
            return_distance = _path_distance(return_path, distances)
            total_distance += return_distance
            elapsed_minutes += return_distance / speed_kmh * 60.0
            route_nodes.extend(return_path[1:])
        else:
            skipped.append({"order_id": "RETURN", "pickup": current, "drop": start})

    delivered = len(stops)
    return {
        "stops": stops,
        "legs": legs,
        "route_nodes": route_nodes,
        "distance_km": total_distance,
        "time_minutes": elapsed_minutes,
        "return_distance_km": return_distance,
        "completed_count": delivered,
        "on_time_count": sum(bool(stop["on_time"]) for stop in stops),
        "on_time_pct": (100.0 * sum(bool(stop["on_time"]) for stop in stops) / delivered) if delivered else 0.0,
        "profit": sum(float(stop["profit"]) for stop in stops),
        "skipped": skipped,
    }

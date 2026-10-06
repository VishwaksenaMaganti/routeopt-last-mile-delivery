"""Dynamic-programming selection for delivery orders."""

from __future__ import annotations

from math import ceil, floor, isfinite
from typing import Mapping, Sequence

WEIGHT_UNITS_PER_KG = 10  # The DP capacity is represented in 0.1 kg units.
MAX_DP_CELLS = 1_000_000


def estimate_dp_cells(order_count: int, capacity_kg: float) -> int:
    """Estimate the DP table size and reject inputs too large for an interactive demo."""
    capacity_kg = float(capacity_kg)
    if not isfinite(capacity_kg) or capacity_kg < 0:
        raise ValueError("Vehicle capacity cannot be negative.")
    scaled_capacity = capacity_kg * WEIGHT_UNITS_PER_KG
    if not isfinite(scaled_capacity):
        raise ValueError("Vehicle capacity is too large for the knapsack table.")
    capacity_units = floor(scaled_capacity + 1e-9)
    cells = (int(order_count) + 1) * (capacity_units + 1)
    if cells > MAX_DP_CELLS:
        raise ValueError(
            f"Knapsack selection would need {cells:,} DP cells; the interactive limit is "
            f"{MAX_DP_CELLS:,}. Reduce vehicle capacity or the number of orders."
        )
    return cells


def knapsack_orders(orders: Sequence[Mapping], capacity_kg: float):
    """Select the highest-profit subset under capacity with 0/1 knapsack DP.

    Package weights are rounded up to the next 0.1 kg unit so rounding can never
    admit a load that exceeds the stated vehicle capacity.
    """
    capacity_kg = float(capacity_kg)
    if not isfinite(capacity_kg) or capacity_kg < 0:
        raise ValueError("Vehicle capacity cannot be negative.")
    scaled_capacity = capacity_kg * WEIGHT_UNITS_PER_KG
    if not isfinite(scaled_capacity):
        raise ValueError("Vehicle capacity is too large for the knapsack table.")
    capacity_units = floor(scaled_capacity + 1e-9)
    count = len(orders)
    raw_weights = [float(order["weight_kg"]) for order in orders]
    profits = [float(order["profit"]) for order in orders]
    if any(not isfinite(weight) or weight <= 0 for weight in raw_weights):
        raise ValueError("Every delivery weight must be greater than zero.")
    if any(not isfinite(profit) or profit < 0 for profit in profits):
        raise ValueError("Delivery profit cannot be negative.")
    dp_cells = estimate_dp_cells(count, capacity_kg)
    weights = [
        capacity_units + 1 if weight > capacity_kg
        else ceil(weight * WEIGHT_UNITS_PER_KG - 1e-9)
        for weight in raw_weights
    ]
    values = [[0.0] * (capacity_units + 1) for _ in range(count + 1)]
    take = [[False] * (capacity_units + 1) for _ in range(count + 1)]

    for index in range(1, count + 1):
        weight, profit = weights[index - 1], profits[index - 1]
        for room in range(capacity_units + 1):
            values[index][room] = values[index - 1][room]
            if weight <= room:
                included = profit + values[index - 1][room - weight]
                if included > values[index][room]:
                    values[index][room] = included
                    take[index][room] = True

    chosen_indices: list[int] = []
    remaining = capacity_units
    for index in range(count, 0, -1):
        if take[index][remaining]:
            chosen_indices.append(index - 1)
            remaining -= weights[index - 1]
    chosen_indices.reverse()
    selected = [dict(orders[index]) for index in chosen_indices]
    return {
        "selected": selected,
        "profit": sum(float(order["profit"]) for order in selected),
        "weight_kg": sum(float(order["weight_kg"]) for order in selected),
        "capacity_units": capacity_units,
        "dp_cells": dp_cells,
    }

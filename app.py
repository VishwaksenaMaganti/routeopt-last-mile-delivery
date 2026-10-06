from __future__ import annotations

import hashlib
import json
import math
from time import perf_counter_ns

import pandas as pd
import streamlit as st

from routeopt.graph import build_adjacency, dijkstra, floyd_warshall, kruskal, prim, reconstruct_path
from routeopt.optimization import MAX_DP_CELLS, estimate_dp_cells, knapsack_orders
from routeopt.sample_data import SAMPLE_EDGES, SAMPLE_NODES, SAMPLE_ORDERS, SAMPLE_VEHICLE
from routeopt.scheduling import greedy_delivery_route
from routeopt.visualization import graph_figure


st.set_page_config(page_title="RouteOpt | Delivery Lab", page_icon="🚚", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #f4f7f8; color: #14252c; }
    [data-testid="stHeader"] { background: rgba(244,247,248,.9); }
    .block-container { padding-top: 1.45rem; padding-bottom: 2.5rem; max-width: 1480px; }
    .hero { background: linear-gradient(115deg,#12343b 0%,#176c68 100%); color: #f8fafc;
            padding: 1.55rem 1.8rem; border-radius: 18px; margin-bottom: 1rem; }
    .hero h1 { font-size: 2.1rem; margin: 0 0 .2rem 0; color: #fff; }
    .hero p { margin: 0; color: #d7eeee; font-size: 1rem; }
    .eyebrow { text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; font-weight: 700; color: #b6e1d8; }
    .soft-card { background: white; border: 1px solid #e3ebed; border-radius: 14px; padding: 1rem 1.1rem; }
    .note { border-left: 4px solid #e5a93d; background: #fff8e8; padding: .75rem 1rem; border-radius: 4px 10px 10px 4px; }
    div[data-testid="stMetric"] { background: white; border: 1px solid #e3ebed; padding: .8rem 1rem; border-radius: 12px; }
    .stButton > button[kind="primary"] { background: #0f766e; border-color: #0f766e; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _initialise_state() -> None:
    st.session_state.setdefault("nodes", [dict(row) for row in SAMPLE_NODES])
    st.session_state.setdefault("edges", [dict(row) for row in SAMPLE_EDGES])
    st.session_state.setdefault("orders", [dict(row) for row in SAMPLE_ORDERS])
    st.session_state.setdefault("capacity_kg", SAMPLE_VEHICLE["capacity_kg"])
    st.session_state.setdefault("speed_kmh", SAMPLE_VEHICLE["speed_kmh"])
    st.session_state.setdefault("start_node", SAMPLE_VEHICLE["start"])
    st.session_state.setdefault("return_to_start", SAMPLE_VEHICLE["return_to_start"])
    st.session_state.setdefault("optimization", None)
    st.session_state.setdefault("last_signature", None)
    st.session_state.setdefault("computed_signature", None)
    st.session_state.setdefault("experiment", None)
    st.session_state.setdefault("source_search", None)
    st.session_state.setdefault("all_pairs", None)
    st.session_state.setdefault("mst_result", None)


def _reset_sample() -> None:
    for key in ("nodes", "edges", "orders", "capacity_kg", "speed_kmh", "start_node", "return_to_start",
                "optimization", "last_signature", "computed_signature", "experiment", "source_search", "all_pairs", "mst_result",
                "knapsack_result", "greedy_result", "nodes_editor", "edges_editor", "orders_editor"):
        st.session_state.pop(key, None)
    _initialise_state()


def _to_records(value) -> list[dict]:
    if value is None:
        return []
    frame = value if isinstance(value, pd.DataFrame) else pd.DataFrame(value)
    rows = frame.to_dict(orient="records")
    clean = []
    for row in rows:
        if all(pd.isna(value) for value in row.values()):
            continue
        clean.append({key: (None if pd.isna(value) else value) for key, value in row.items()})
    return clean


def _signature(nodes, edges, orders, capacity, speed, start, return_to_start) -> str:
    data = {"nodes": nodes, "edges": edges, "orders": orders, "capacity": capacity,
            "speed": speed, "start": start, "return": return_to_start}
    raw = json.dumps(data, sort_keys=True, default=str, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate(nodes, edges, orders, capacity, speed, start):
    errors = []
    node_ids = [str(row.get("node", "")).strip() for row in nodes]
    if not node_ids or any(not node for node in node_ids):
        errors.append("Add at least one location and give each location a short ID.")
    if len(set(node_ids)) != len(node_ids):
        errors.append("Location IDs must be unique.")
    known = set(node_ids)
    if start not in known:
        errors.append("The vehicle start location must exist in the network.")
    if not math.isfinite(float(capacity)) or not math.isfinite(float(speed)) or float(capacity) <= 0 or float(speed) <= 0:
        errors.append("Vehicle capacity and speed must be greater than zero.")
    else:
        try:
            estimate_dp_cells(len(orders), float(capacity))
        except ValueError as error:
            errors.append(str(error))
    seen_edges = set()
    for index, row in enumerate(edges, start=1):
        first, second = str(row.get("from", "")), str(row.get("to", ""))
        try:
            distance = float(row.get("distance_km", 0))
        except (TypeError, ValueError):
            distance = 0
        if first not in known or second not in known:
            errors.append(f"Road {index} refers to a location that is not in the network.")
        elif first == second:
            errors.append(f"Road {index} connects a location to itself.")
        elif not math.isfinite(distance) or distance <= 0:
            errors.append(f"Road {index} must have a positive distance.")
        key = tuple(sorted((first, second)))
        if key in seen_edges:
            errors.append(f"Road {index} repeats a road that is already listed.")
        seen_edges.add(key)
    seen_orders = set()
    for index, row in enumerate(orders, start=1):
        order_id = str(row.get("order_id", "")).strip()
        if not order_id:
            errors.append(f"Delivery {index} needs an order ID.")
        if order_id in seen_orders:
            errors.append(f"Order IDs must be unique ({order_id}).")
        seen_orders.add(order_id)
        if str(row.get("pickup", "")) not in known or str(row.get("drop", "")) not in known:
            errors.append(f"Delivery {order_id or index} uses a pickup or drop location outside the network.")
        elif str(row.get("pickup", "")) == str(row.get("drop", "")):
            errors.append(f"Delivery {order_id or index} must have different pickup and drop locations.")
        try:
            weight = float(row.get("weight_kg", 0))
            profit = float(row.get("profit", 0))
            deadline = float(row.get("deadline_hr", 0))
            service = float(row.get("service_minutes", 0))
        except (TypeError, ValueError):
            errors.append(f"Delivery {order_id or index} has a non-numeric value.")
            continue
        if (not all(math.isfinite(value) for value in (weight, profit, deadline, service))
                or weight <= 0 or profit < 0 or deadline <= 0 or service < 0):
            errors.append(f"Delivery {order_id or index} needs positive weight and deadline, non-negative profit and service time.")
    return errors


def _run_pipeline(nodes, edges, orders, capacity, speed, start, return_to_start):
    node_ids = [str(row["node"]) for row in nodes]
    edge_tuples = [(str(row["from"]), str(row["to"]), float(row["distance_km"])) for row in edges]
    adjacency = build_adjacency(node_ids, edge_tuples)
    timing = {}

    before = perf_counter_ns()
    distances, next_hop = floyd_warshall(adjacency)
    timing["Floyd-Warshall"] = (perf_counter_ns() - before) / 1000.0

    before = perf_counter_ns()
    selection = knapsack_orders(orders, float(capacity))
    timing["0/1 Knapsack DP"] = (perf_counter_ns() - before) / 1000.0

    before = perf_counter_ns()
    route = greedy_delivery_route(selection["selected"], start, distances, next_hop, float(speed), return_to_start)
    timing["Greedy scheduling heuristic"] = (perf_counter_ns() - before) / 1000.0

    before = perf_counter_ns()
    prim_result = prim(node_ids, edge_tuples)
    timing["Prim MST"] = (perf_counter_ns() - before) / 1000.0
    before = perf_counter_ns()
    kruskal_result = kruskal(node_ids, edge_tuples)
    timing["Kruskal MST"] = (perf_counter_ns() - before) / 1000.0
    before = perf_counter_ns()
    for source in node_ids:
        dijkstra(adjacency, source)
    timing["Dijkstra (all sources)"] = (perf_counter_ns() - before) / 1000.0

    selected_ids = {str(row["order_id"]) for row in selection["selected"]}
    scheduled_ids = {str(row["order_id"]) for row in route["stops"]}
    route["unreachable"] = sorted(selected_ids - scheduled_ids)
    route["selected_count"] = len(selection["selected"])
    route["selected_weight_kg"] = selection["weight_kg"]
    route["selected_profit"] = selection["profit"]
    route["capacity_utilization_pct"] = min(100.0, 100.0 * selection["weight_kg"] / float(capacity))
    route["completed_profit"] = sum(float(row["profit"]) for row in route["stops"])
    route["distance_km"] = float(route["distance_km"])
    return {
        "selection": selection,
        "route": route,
        "distances": distances,
        "next_hop": next_hop,
        "timing_us": timing,
        "prim": prim_result,
        "kruskal": kruskal_result,
    }


_initialise_state()
with st.sidebar:
    st.markdown("### Vehicle setup")
    capacity = st.number_input("Payload capacity (kg)", min_value=0.1, max_value=10000.0, step=1.0, key="capacity_kg")
    speed = st.number_input("Average speed (km/h)", min_value=0.1, max_value=300.0, step=1.0, key="speed_kmh")
    current_node_ids = [str(row.get("node", "")) for row in st.session_state.nodes if str(row.get("node", ""))]
    if current_node_ids and st.session_state.start_node not in current_node_ids:
        st.session_state.start_node = current_node_ids[0]
    start = st.selectbox("Starting location", current_node_ids or ["W"], key="start_node")
    return_to_start = st.checkbox("Return to start after deliveries", key="return_to_start")
    st.divider()
    st.caption("Weights in the DP table use 0.1 kg units. Deadlines are hours after departure.")
    st.button("Reset to sample scenario", use_container_width=True, on_click=_reset_sample)

st.markdown(
    "<div class='hero'><div class='eyebrow'>Design and Analysis of Algorithms</div>"
    "<h1>RouteOpt Delivery Lab</h1><p>Explore shortest paths, capacity planning, and deadline-aware delivery routing.</p></div>",
    unsafe_allow_html=True,
)

with st.expander("1. Edit the road network", expanded=True):
    node_frame = pd.DataFrame(st.session_state.nodes, columns=["node", "label", "kind"])
    node_edit = st.data_editor(
        node_frame, key="nodes_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "node": st.column_config.TextColumn("Location ID", help="Short, unique ID such as W, P1, or D1."),
            "label": st.column_config.TextColumn("Display name"),
            "kind": st.column_config.SelectboxColumn("Location type", options=["Warehouse", "Pickup", "Delivery", "Waypoint"]),
        },
    )
    st.session_state.nodes = _to_records(node_edit)
    valid_node_ids = [str(row.get("node", "")) for row in st.session_state.nodes if str(row.get("node", ""))]
    if valid_node_ids and st.session_state.start_node not in valid_node_ids:
        st.session_state.start_node = valid_node_ids[0]
    edge_frame = pd.DataFrame(st.session_state.edges, columns=["from", "to", "distance_km"])
    edge_edit = st.data_editor(
        edge_frame, key="edges_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "from": st.column_config.SelectboxColumn("From", options=valid_node_ids),
            "to": st.column_config.SelectboxColumn("To", options=valid_node_ids),
            "distance_km": st.column_config.NumberColumn("Road distance (km)", min_value=0.01, step=0.5, format="%.2f km"),
        },
    )
    st.session_state.edges = _to_records(edge_edit)

with st.expander("2. Edit delivery orders", expanded=True):
    order_frame = pd.DataFrame(st.session_state.orders, columns=["order_id", "pickup", "drop", "weight_kg", "profit", "deadline_hr", "service_minutes"])
    order_edit = st.data_editor(
        order_frame, key="orders_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "order_id": st.column_config.TextColumn("Order ID"),
            "pickup": st.column_config.SelectboxColumn("Pickup", options=valid_node_ids),
            "drop": st.column_config.SelectboxColumn("Drop", options=valid_node_ids),
            "weight_kg": st.column_config.NumberColumn("Weight (kg)", min_value=0.1, step=0.5, format="%.1f kg"),
            "profit": st.column_config.NumberColumn("Profit (INR)", min_value=0.0, step=100.0, format="₹%.0f"),
            "deadline_hr": st.column_config.NumberColumn("Deadline (hours)", min_value=0.01, step=0.25, format="%.2f h"),
            "service_minutes": st.column_config.NumberColumn("Handling time (min)", min_value=0.0, step=1.0, format="%.0f min"),
        },
    )
    st.session_state.orders = _to_records(order_edit)

nodes, edges, orders = st.session_state.nodes, st.session_state.edges, st.session_state.orders
capacity, speed, start, return_to_start = (
    st.session_state.capacity_kg, st.session_state.speed_kmh,
    st.session_state.start_node, st.session_state.return_to_start,
)
errors = _validate(nodes, edges, orders, capacity, speed, start)
input_signature = _signature(nodes, edges, orders, capacity, speed, start, return_to_start)
if st.session_state.computed_signature and st.session_state.computed_signature != input_signature:
    for key in ("optimization", "experiment", "source_search", "all_pairs", "mst_result", "knapsack_result", "greedy_result"):
        st.session_state[key] = None
    st.session_state.computed_signature = None
    st.session_state.last_signature = None
if errors:
    for message in errors:
        st.error(message)
else:
    if st.session_state.last_signature and st.session_state.last_signature != input_signature:
        st.info("Inputs changed. Run the optimization again to refresh the results.")
    run_col, summary_col = st.columns([1.1, 2.9], vertical_alignment="center")
    with run_col:
        run_all = st.button("Run full optimization", type="primary", use_container_width=True)
    with summary_col:
        st.caption("Pipeline: Dijkstra + Floyd-Warshall, Prim/Kruskal, 0/1 Knapsack DP, then a deadline-aware greedy route heuristic.")
    if run_all:
        with st.spinner("Running shortest paths, capacity selection, and route scheduling..."):
            st.session_state.optimization = _run_pipeline(nodes, edges, orders, capacity, speed, start, return_to_start)
            st.session_state.last_signature = input_signature
            st.session_state.computed_signature = input_signature
        st.success("Optimization complete. Timings below were measured during this run.")

tabs = st.tabs(["Overview", "Network algorithms", "Delivery algorithms", "Experiment"])
with tabs[0]:
    result = st.session_state.optimization
    if result is None:
        st.info("Edit the sample network and orders if needed, then select **Run full optimization**.")
        st.html(graph_figure(nodes, edges))
    else:
        route = result["route"]
        metric_cols = st.columns(5)
        metric_cols[0].metric("Delivered profit", f"₹{route['completed_profit']:,.0f}")
        metric_cols[1].metric("Route distance", f"{route['distance_km']:.1f} km")
        metric_cols[2].metric("Route time", f"{route['time_minutes']:.0f} min")
        metric_cols[3].metric("Capacity used", f"{route['capacity_utilization_pct']:.1f}%")
        metric_cols[4].metric("On-time deliveries", f"{route['on_time_pct']:.1f}%")
        left, right = st.columns([1.55, 1])
        with left:
            st.subheader("Road network and planned route")
            st.html(graph_figure(nodes, edges, route["route_nodes"]))
        with right:
            st.subheader("Route sequence")
            st.write(" → ".join(route["route_nodes"]))
            if route["stops"]:
                route_frame = pd.DataFrame(route["stops"])
                st.dataframe(route_frame[["order_id", "pickup", "drop", "drop_arrival_min", "deadline_min", "on_time", "profit"]],
                             use_container_width=True, hide_index=True,
                             column_config={"drop_arrival_min": st.column_config.NumberColumn("Drop arrival (min)", format="%.1f"),
                                            "deadline_min": st.column_config.NumberColumn("Deadline (min)", format="%.1f"),
                                            "profit": st.column_config.NumberColumn("Profit (INR)", format="₹%.0f")})
                st.download_button(
                    "Download route plan CSV",
                    data=route_frame.to_csv(index=False).encode("utf-8"),
                    file_name="routeopt_route_plan.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            if route["unreachable"]:
                st.warning("Selected orders could not be routed because their locations are disconnected: " + ", ".join(route["unreachable"]))
            st.caption(f"Knapsack selected {route['selected_count']} orders ({route['selected_weight_kg']:.1f} kg). The greedy route is a heuristic and is not guaranteed to be globally optimal.")
        st.subheader("Measured algorithm runtimes")
        timing_frame = pd.DataFrame([{"Algorithm": name, "Measured runtime (µs)": value} for name, value in result["timing_us"].items()])
        st.dataframe(timing_frame, hide_index=True, use_container_width=True,
                     column_config={"Measured runtime (µs)": st.column_config.NumberColumn(format="%.2f µs")})
        st.caption("These timings are measured on this run and depend on the current network, input size, and machine. They are not fixed benchmark claims.")

with tabs[1]:
    st.subheader("Shortest paths and network backbone")
    if valid_node_ids:
        source = st.selectbox("Dijkstra source", valid_node_ids, key="dijkstra_source")
        if st.button("Run Dijkstra from source", key="run_dijkstra") and not errors:
            adjacency = build_adjacency(valid_node_ids, [(str(row["from"]), str(row["to"]), float(row["distance_km"])) for row in edges])
            begin = perf_counter_ns()
            distances, previous = dijkstra(adjacency, source)
            runtime = (perf_counter_ns() - begin) / 1000.0
            st.session_state.source_search = {"source": source, "distances": distances, "previous": previous, "runtime_us": runtime}
            st.session_state.computed_signature = input_signature
        search = st.session_state.source_search
        if search and search["source"] == source:
            st.caption(f"Dijkstra runtime: {search['runtime_us']:.2f} µs")
            rows = []
            for target, distance in search["distances"].items():
                path = reconstruct_path(search["previous"], source, target)
                rows.append({"Destination": target, "Distance (km)": distance if math.isfinite(distance) else None,
                             "Shortest path": " → ".join(path) if path else "Unreachable"})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if st.button("Run Floyd-Warshall all-pairs", key="run_floyd") and not errors:
        adjacency = build_adjacency(valid_node_ids, [(str(row["from"]), str(row["to"]), float(row["distance_km"])) for row in edges])
        begin = perf_counter_ns()
        distances, next_hop = floyd_warshall(adjacency)
        runtime = (perf_counter_ns() - begin) / 1000.0
        st.session_state.all_pairs = {"distances": distances, "next_hop": next_hop, "runtime_us": runtime}
        st.session_state.computed_signature = input_signature
    if st.session_state.all_pairs:
        all_pairs = st.session_state.all_pairs
        st.caption(f"Floyd-Warshall runtime: {all_pairs['runtime_us']:.2f} µs")
        matrix = pd.DataFrame(all_pairs["distances"], index=valid_node_ids).replace(math.inf, "∞")
        st.dataframe(matrix, use_container_width=True)
    mst_method = st.radio("Minimum spanning tree method", ["Prim", "Kruskal"], horizontal=True, key="mst_method")
    if st.button("Run selected MST algorithm", key="run_mst") and not errors:
        edge_tuples = [(str(row["from"]), str(row["to"]), float(row["distance_km"])) for row in edges]
        begin = perf_counter_ns()
        forest, total, components = (prim(valid_node_ids, edge_tuples) if mst_method == "Prim" else kruskal(valid_node_ids, edge_tuples))
        runtime = (perf_counter_ns() - begin) / 1000.0
        st.session_state.mst_result = {"method": mst_method, "forest": forest, "total": total, "components": components, "runtime_us": runtime}
        st.session_state.computed_signature = input_signature
    mst = st.session_state.mst_result
    if mst:
        st.write(f"**{mst['method']}** minimum spanning forest: {mst['total']:.2f} km across {mst['components']} connected component(s). Runtime: {mst['runtime_us']:.2f} µs.")
        st.html(graph_figure(nodes, edges, tree_edges=mst["forest"]))
        st.dataframe(pd.DataFrame(mst["forest"], columns=["From", "To", "Distance (km)"]), hide_index=True, use_container_width=True)

with tabs[2]:
    st.subheader("Capacity selection and delivery ordering")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run 0/1 Knapsack DP", key="run_knapsack") and not errors:
            begin = perf_counter_ns()
            selection = knapsack_orders(orders, float(capacity))
            runtime = (perf_counter_ns() - begin) / 1000.0
            st.session_state.knapsack_result = {**selection, "runtime_us": runtime}
            st.session_state.computed_signature = input_signature
        selection = st.session_state.get("knapsack_result")
        if selection:
            st.metric("DP-selected profit", f"₹{selection['profit']:,.0f}")
            st.write(f"Selected load: {selection['weight_kg']:.1f} kg of {float(capacity):.1f} kg; DP table cells: {selection['dp_cells']:,} (interactive limit: {MAX_DP_CELLS:,}); runtime: {selection['runtime_us']:.2f} µs.")
            st.dataframe(pd.DataFrame(selection["selected"]), hide_index=True, use_container_width=True)
    with c2:
        if st.button("Run Greedy delivery schedule", key="run_greedy") and not errors:
            adjacency = build_adjacency(valid_node_ids, [(str(row["from"]), str(row["to"]), float(row["distance_km"])) for row in edges])
            distances, next_hop = floyd_warshall(adjacency)
            selection = st.session_state.get("knapsack_result")
            if not selection:
                selection = knapsack_orders(orders, float(capacity))
                st.session_state.knapsack_result = selection
            begin = perf_counter_ns()
            route = greedy_delivery_route(selection["selected"], start, distances, next_hop, float(speed), return_to_start)
            runtime = (perf_counter_ns() - begin) / 1000.0
            st.session_state.greedy_result = {**route, "runtime_us": runtime}
            st.session_state.computed_signature = input_signature
        route = st.session_state.get("greedy_result")
        if route:
            st.metric("On-time delivery rate", f"{route['on_time_pct']:.1f}%")
            st.write(f"Route: {' → '.join(route['route_nodes'])}")
            st.write(f"Distance: {route['distance_km']:.2f} km | Travel + handling time: {route['time_minutes']:.1f} min | Runtime: {route['runtime_us']:.2f} µs")
            st.caption("Priority score = 0.45 × deadline urgency + 0.35 × normalized profit per delivery hour + 0.20 × normalized travel efficiency. This is a heuristic, not a global-optimality guarantee.")
            st.dataframe(pd.DataFrame(route["stops"]), hide_index=True, use_container_width=True)

with tabs[3]:
    st.subheader("Algorithm comparison and small experiment")
    st.write("Compare single-source Dijkstra run from every vertex with one Floyd-Warshall all-pairs run. Also compare Prim and Kruskal on the same road graph.")
    if st.button("Run comparison experiment", key="run_experiment") and not errors:
        node_ids = [str(row["node"]) for row in nodes]
        edge_tuples = [(str(row["from"]), str(row["to"]), float(row["distance_km"])) for row in edges]
        adjacency = build_adjacency(node_ids, edge_tuples)
        begin = perf_counter_ns()
        fw_distances, _ = floyd_warshall(adjacency)
        fw_us = (perf_counter_ns() - begin) / 1000.0
        begin = perf_counter_ns()
        dijkstra_distances = {source: dijkstra(adjacency, source)[0] for source in node_ids}
        dij_us = (perf_counter_ns() - begin) / 1000.0
        identical = all(
            (math.isinf(dijkstra_distances[source][target]) and math.isinf(fw_distances[source][target]))
            or math.isclose(dijkstra_distances[source][target], fw_distances[source][target], rel_tol=1e-9, abs_tol=1e-9)
            for source in node_ids for target in node_ids
        )
        begin = perf_counter_ns()
        prim_result = prim(node_ids, edge_tuples)
        prim_us = (perf_counter_ns() - begin) / 1000.0
        begin = perf_counter_ns()
        kruskal_result = kruskal(node_ids, edge_tuples)
        kruskal_us = (perf_counter_ns() - begin) / 1000.0
        st.session_state.experiment = {
            "rows": [
                {"Algorithm": "Dijkstra (all sources)", "Measured time (µs)": dij_us, "Operation/result": f"{len(node_ids)} source runs"},
                {"Algorithm": "Floyd-Warshall", "Measured time (µs)": fw_us, "Operation/result": f"{len(node_ids)} × {len(node_ids)} distance matrix"},
                {"Algorithm": "Prim", "Measured time (µs)": prim_us, "Operation/result": f"{len(prim_result[0])} backbone edge(s), {prim_result[1]:.2f} km"},
                {"Algorithm": "Kruskal", "Measured time (µs)": kruskal_us, "Operation/result": f"{len(kruskal_result[0])} backbone edge(s), {kruskal_result[1]:.2f} km"},
            ],
            "equivalent": identical,
            "same_mst_weight": math.isclose(prim_result[1], kruskal_result[1], rel_tol=1e-9, abs_tol=1e-9),
            "vertices": len(node_ids), "roads": len(edge_tuples),
        }
        st.session_state.computed_signature = input_signature
    experiment = st.session_state.experiment
    if experiment:
        st.write(f"Current graph: **{experiment['vertices']} locations**, **{experiment['roads']} roads**.")
        st.dataframe(pd.DataFrame(experiment["rows"]), hide_index=True, use_container_width=True,
                     column_config={"Measured time (µs)": st.column_config.NumberColumn(format="%.2f µs")})
        st.success(f"Shortest-path distance tables agree: {experiment['equivalent']}. Prim and Kruskal forest weights agree: {experiment['same_mst_weight']}.")
        st.caption("Runtimes are measured afresh when the experiment is run. For a defensible study, repeat runs over increasing graph sizes and report the environment, medians, and input counts.")

st.divider()
st.caption("RouteOpt is an educational DAA prototype. The greedy ordering stage is a heuristic and does not guarantee the globally optimal route.")

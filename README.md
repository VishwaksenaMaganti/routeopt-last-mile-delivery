# RouteOpt - Last-Mile Delivery Optimization System

RouteOpt is a Python and Streamlit demonstration of how Design and Analysis of Algorithms techniques can support a small last-mile delivery operation. It models roads as an undirected weighted graph, selects profitable orders within a vehicle's payload limit, and builds a deadline-aware route with an explicitly heuristic greedy rule.

## Features

- Editable locations, road distances, delivery orders, vehicle capacity, speed, start location, and return-to-start option.
- Weighted adjacency-list graph representation.
- Dijkstra single-source shortest paths with a min-priority queue and reconstructable paths.
- Floyd-Warshall all-pairs shortest paths and distance matrix.
- Prim and Kruskal minimum spanning forest comparisons.
- 0/1 Knapsack dynamic programming for profit-maximizing delivery selection under capacity.
- Greedy pickup/drop ordering that considers deadline slack, profit per estimated delivery hour, and travel efficiency.
- Responsive road network, route, and spanning-forest visualizations with hover labels.
- Route profit, distance, estimated time, selected load, capacity utilization, on-time delivery percentage, and runtimes measured when algorithms run.
- CSV export of the planned delivery stops.
- A comparison experiment that checks Dijkstra/Floyd-Warshall distance agreement and Prim/Kruskal forest weight agreement on the current graph.

## Requirements

- Python 3.10 or later
- Packages listed in `requirements.txt`

## Run on Windows

For one-click startup, double-click **`Start-RouteOpt.bat`** in this folder. The first run creates a local virtual environment and installs dependencies if needed. Leave the command window open while using RouteOpt; press **Ctrl+C** in that window to stop the app.

To start it manually, open PowerShell in this project directory and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks virtual-environment activation, run the app without activating it:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit prints a local URL (usually `http://localhost:8501`) to open in a browser.

## Run on macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

## Demo walkthrough

1. Start with the sample network and orders, or edit the location, road, and delivery tables.
2. Set the vehicle payload, average speed, start location, and optional return trip in the sidebar.
3. Select **Run full optimization** to run shortest paths, the two MST algorithms, knapsack selection, and the greedy route stage.
4. Use **Network algorithms** to run Dijkstra, Floyd-Warshall, Prim, or Kruskal separately.
5. Use **Delivery algorithms** to run 0/1 Knapsack and the greedy delivery schedule separately.
6. Use **Experiment** to compare measured runtimes and verify algorithm result agreement for the current graph.

## Data and metric rules

- Road segments are undirected and use positive distances in kilometres; zero-length roads are not accepted.
- The vehicle speed is held constant; estimated travel minutes equal distance divided by speed.
- Order deadlines are measured in hours after departure. Handling time is added to total route time after each delivery; a delivery is on time when the drop-off arrival is no later than its deadline.
- The knapsack table stores weights in 0.1 kg units. Each package weight is rounded up to a unit, and vehicle capacity is rounded down, preventing rounding from exceeding the stated capacity.
- To keep the interactive app responsive, the knapsack stage is limited to 1,000,000 DP table cells; the app explains when the current order count and capacity exceed that limit.
- Capacity utilization is the knapsack-selected package weight divided by vehicle capacity. If a selected order is unreachable, it remains in the selected-load measure and is separately reported as unreachable.
- On-time percentage is based on orders reached by the route scheduler. If no order can be routed, the percentage is 0%.
- Distance includes an optional return leg when **Return to start after deliveries** is selected.
- Runtimes are measured with Python's high-resolution performance counter on the current run. They vary by machine, graph, inputs, and run conditions; no benchmark results are prefilled.

## Algorithm notes

| Algorithm | Purpose | Time complexity |
|---|---|---|
| Dijkstra with binary heap | Shortest paths from one source | `O((V + E) log V)` |
| Floyd-Warshall | Shortest paths between every pair | `O(V^3)` |
| Prim with binary heap | Minimum spanning forest | `O((V + E) log V)` |
| Kruskal with disjoint sets | Minimum spanning forest | `O(E log E)` |
| 0/1 Knapsack DP | Select a high-profit subset within capacity | `O(nC)` time and space, where `C` is capacity in 0.1 kg units |

Prim/Kruskal show a low-distance network backbone; they do not determine the delivery route. Knapsack selection optimizes profit under weight capacity but does not itself model deadlines or road connectivity.

## Greedy route heuristic

After capacity selection, each remaining order is scored at every route step:

```text
priority = 0.45 * deadline_urgency
         + 0.35 * normalized_profit_per_delivery_hour
         + 0.20 * normalized_travel_efficiency
```

The scheduler estimates the current-location-to-pickup and pickup-to-drop travel using the all-pairs distance matrix, then takes the highest-scoring reachable order. **This stage is a heuristic and is not guaranteed to find the globally optimal pickup/drop route.** The knapsack and route stages are intentionally separate so their decisions can be inspected during a DAA demonstration.

## Project structure

```text
app.py                       Streamlit interface and runtime measurements
routeopt/graph.py            Adjacency lists, Dijkstra, Floyd-Warshall, Prim, Kruskal
routeopt/optimization.py     0/1 Knapsack DP
routeopt/scheduling.py       Greedy deadline-aware route heuristic
routeopt/visualization.py    Responsive SVG network/route drawing
routeopt/sample_data.py      Editable demo scenario
requirements.txt             Runtime dependencies
```

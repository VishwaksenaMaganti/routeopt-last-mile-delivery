"""Small deterministic scenario used by the app and the report examples."""

SAMPLE_NODES = [
    {"node": "W", "label": "Warehouse", "kind": "Warehouse"},
    {"node": "P1", "label": "Pickup North", "kind": "Pickup"},
    {"node": "D1", "label": "Drop North", "kind": "Delivery"},
    {"node": "P2", "label": "Pickup East", "kind": "Pickup"},
    {"node": "D2", "label": "Drop East", "kind": "Delivery"},
    {"node": "P3", "label": "Pickup South", "kind": "Pickup"},
    {"node": "D3", "label": "Drop South", "kind": "Delivery"},
]

SAMPLE_EDGES = [
    {"from": "W", "to": "P1", "distance_km": 2.0},
    {"from": "P1", "to": "D1", "distance_km": 4.0},
    {"from": "W", "to": "P2", "distance_km": 4.0},
    {"from": "P2", "to": "D2", "distance_km": 2.0},
    {"from": "D1", "to": "P2", "distance_km": 2.0},
    {"from": "D1", "to": "P3", "distance_km": 3.0},
    {"from": "D2", "to": "P3", "distance_km": 2.0},
    {"from": "P3", "to": "D3", "distance_km": 2.0},
    {"from": "D2", "to": "D3", "distance_km": 3.0},
    {"from": "W", "to": "D1", "distance_km": 5.0},
]

SAMPLE_ORDERS = [
    {"order_id": "RO-101", "pickup": "P1", "drop": "D1", "weight_kg": 8.0, "profit": 1200.0, "deadline_hr": 1.0, "service_minutes": 5.0},
    {"order_id": "RO-102", "pickup": "P2", "drop": "D2", "weight_kg": 12.0, "profit": 1800.0, "deadline_hr": 1.25, "service_minutes": 5.0},
    {"order_id": "RO-103", "pickup": "P3", "drop": "D3", "weight_kg": 10.0, "profit": 1500.0, "deadline_hr": 1.5, "service_minutes": 5.0},
    {"order_id": "RO-104", "pickup": "P1", "drop": "D2", "weight_kg": 18.0, "profit": 2300.0, "deadline_hr": 1.4, "service_minutes": 5.0},
]

SAMPLE_VEHICLE = {"capacity_kg": 30.0, "speed_kmh": 30.0, "start": "W", "return_to_start": False}


"""
Export analysis results to JSON for the Three.js visualization.

Converts r5py DetailedItineraries GeoDataFrames into the compact JSON format
that the visualization layer expects.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from analysis.config import (
    EXPORT_DIR,
    VIZ_CENTER,
    VIZ_BBOX,
    MODE_COLORS,
    SCENARIOS,
    TIME_WINDOWS,
)


def extract_coords(geometry) -> list:
    """Extract coordinate list from LineString or MultiLineString geometry."""
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return list(geometry.coords)
    if geometry.geom_type == "MultiLineString":
        coords = []
        for part in geometry.geoms:
            coords.extend(list(part.coords))
        return coords
    return []


def simplify_path(coords: list, tolerance: float = 0.0001) -> list:
    """
    Simplify a coordinate path using Douglas-Peucker algorithm.
    Reduces JSON file size while preserving route shape.

    Args:
        coords: list of [lng, lat] pairs
        tolerance: simplification tolerance in degrees (~11m at this latitude)
    """
    if len(coords) < 3:
        return coords

    line = LineString([(c[0], c[1]) for c in coords])
    simplified = line.simplify(tolerance, preserve_topology=True)
    return [[round(c[0], 6), round(c[1], 6)] for c in simplified.coords]


def export_trips(
    scenario_name: str,
    mode_choice_df: pd.DataFrame,
    car_itineraries: gpd.GeoDataFrame,
    transit_itineraries: gpd.GeoDataFrame,
    bike_itineraries: gpd.GeoDataFrame = None,
    road_segments: dict = None,
):
    """
    Export trip data as JSON for the visualization.

    Each trip includes: id, mode, departure time, duration, path coordinates.
    """
    print(f"  Exporting trips for {scenario_name}...")

    trips = []
    trip_id = 0

    # Process car itineraries
    if car_itineraries is not None and len(car_itineraries) > 0:
        for (from_id, to_id), group in car_itineraries.groupby(["from_id", "to_id"]):
            # Get departure time from mode_choice_df
            match = mode_choice_df[
                (mode_choice_df["from_id"] == from_id) &
                (mode_choice_df["to_id"] == to_id)
            ]
            dep_seconds = int(match["departure_seconds"].iloc[0]) if len(match) > 0 else 3600

            # Check if this trip's chosen mode is CAR
            chosen = match["chosen_mode"].iloc[0] if len(match) > 0 else "CAR"
            if chosen != "CAR":
                continue

            # Use BPR-congested duration if available (agents slow down with traffic).
            # Falls back to raw r5py itinerary time if congestion wasn't computed.
            congested_min = None
            if len(match) > 0 and "car_minutes_congested" in match.columns:
                val = match["car_minutes_congested"].iloc[0]
                if pd.notna(val) and val > 0:
                    congested_min = val
            if congested_min is not None:
                duration_sec = congested_min * 60
            else:
                total_time = group["travel_time"].sum()
                if pd.isna(total_time):
                    continue
                duration_sec = total_time.total_seconds()
            if duration_sec <= 0:
                continue

            # Extract path geometry
            path_coords = []
            for _, leg in group.iterrows():
                raw = extract_coords(leg.geometry)
                if raw:
                    path_coords.extend([[round(c[0], 6), round(c[1], 6)] for c in raw])

            if not path_coords:
                continue

            path_coords = simplify_path(path_coords)

            trips.append({
                "id": f"t_{trip_id}",
                "mode": "CAR",
                "departure": dep_seconds,
                "duration": int(duration_sec),
                "path": path_coords,
            })
            trip_id += 1

    # Process transit itineraries
    if transit_itineraries is not None and len(transit_itineraries) > 0:
        for (from_id, to_id), group in transit_itineraries.groupby(["from_id", "to_id"]):
            total_time = group["travel_time"].sum()
            if pd.isna(total_time):
                continue
            duration_sec = total_time.total_seconds()
            if duration_sec <= 0:
                continue

            match = mode_choice_df[
                (mode_choice_df["from_id"] == from_id) &
                (mode_choice_df["to_id"] == to_id)
            ]
            dep_seconds = int(match["departure_seconds"].iloc[0]) if len(match) > 0 else 3600
            chosen = match["chosen_mode"].iloc[0] if len(match) > 0 else "TRANSIT"
            if chosen != "TRANSIT":
                continue

            path_coords = []
            for _, leg in group.iterrows():
                raw = extract_coords(leg.geometry)
                if raw:
                    path_coords.extend([[round(c[0], 6), round(c[1], 6)] for c in raw])

            if not path_coords:
                continue

            path_coords = simplify_path(path_coords)

            trips.append({
                "id": f"t_{trip_id}",
                "mode": "TRANSIT",
                "departure": dep_seconds,
                "duration": int(duration_sec),
                "path": path_coords,
            })
            trip_id += 1

    # Process bike itineraries
    if bike_itineraries is not None and len(bike_itineraries) > 0:
        for (from_id, to_id), group in bike_itineraries.groupby(["from_id", "to_id"]):
            total_time = group["travel_time"].sum()
            if pd.isna(total_time):
                continue
            duration_sec = total_time.total_seconds()
            if duration_sec <= 0:
                continue

            match = mode_choice_df[
                (mode_choice_df["from_id"] == from_id) &
                (mode_choice_df["to_id"] == to_id)
            ]
            dep_seconds = int(match["departure_seconds"].iloc[0]) if len(match) > 0 else 3600
            chosen = match["chosen_mode"].iloc[0] if len(match) > 0 else "BICYCLE"
            if chosen != "BICYCLE":
                continue

            path_coords = []
            for _, leg in group.iterrows():
                raw = extract_coords(leg.geometry)
                if raw:
                    path_coords.extend([[round(c[0], 6), round(c[1], 6)] for c in raw])

            if not path_coords:
                continue

            path_coords = simplify_path(path_coords)

            trips.append({
                "id": f"t_{trip_id}",
                "mode": "BICYCLE",
                "departure": dep_seconds,
                "duration": int(duration_sec),
                "path": path_coords,
            })
            trip_id += 1

    # Write to JSON
    output = {
        "type": "trips",
        "scenario": scenario_name,
        "count": len(trips),
        "trips": trips,
    }

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORT_DIR / f"trips_{scenario_name}.json"
    with open(out_path, "w") as f:
        json.dump(output, f)

    size_mb = out_path.stat().st_size / 1e6
    print(f"    Exported {len(trips)} trips to {out_path} ({size_mb:.1f} MB)")

    # Breakdown by mode
    mode_counts = {}
    for t in trips:
        mode_counts[t["mode"]] = mode_counts.get(t["mode"], 0) + 1
    for mode, count in sorted(mode_counts.items()):
        print(f"      {mode}: {count} trips")


def export_metadata(all_stats: dict):
    """
    Export metadata JSON with study area info and aggregate statistics.
    """
    metadata = {
        "study_area": {
            "center": [VIZ_CENTER["lng"], VIZ_CENTER["lat"]],
            "bbox": VIZ_BBOX,
        },
        "time_range": {
            "start": "07:00",
            "end": "09:30",
            "duration_seconds": 9000,
        },
        "scenarios": {},
        "mode_colors": MODE_COLORS,
        "stats": {},
    }

    for name, scenario in SCENARIOS.items():
        metadata["scenarios"][name] = {
            "label": scenario["label"],
            "description": scenario["description"],
        }

    for name, stats in all_stats.items():
        metadata["stats"][name] = {
            "car_pct": stats.get("car_pct", 0),
            "transit_pct": stats.get("transit_pct", 0),
            "bicycle_pct": stats.get("bicycle_pct", 0),
            "walk_pct": stats.get("walk_pct", 0),
            "total_trips": stats.get("total_trips", 0),
        }

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORT_DIR / "metadata.json"
    with open(out_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  Exported metadata to {out_path}")

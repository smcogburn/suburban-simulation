"""
Congestion approximation using the BPR (Bureau of Public Roads) volume-delay function.

Takes car trip data and road network properties to estimate realistic congested
travel times and per-road-segment congestion ratios for visualization.

BPR formula: congested_time = free_flow_time * (1 + alpha * (volume / capacity) ^ beta)
"""

import json
from collections import defaultdict

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import nearest_points

from analysis.config import (
    BPR_ALPHA,
    BPR_BETA,
    TIME_WINDOWS,
    TRIP_SCALE_FACTOR,
    EXPORT_DIR,
)


def assign_trips_to_segments(
    trip_geometries: gpd.GeoDataFrame,
    road_segments: dict,
    departure_seconds: pd.Series,
) -> dict:
    """
    Map each car trip to the road segments it traverses and count trips
    per segment per time window.

    Args:
        trip_geometries: GeoDataFrame with trip LineString geometry
        road_segments: dict from roads.json (loaded road network)
        departure_seconds: Series of departure times (seconds since 7AM)

    Returns:
        dict mapping segment_id -> list of 5 trip counts (one per time window)
    """
    print("  Assigning trips to road segments...")

    # Build a GeoDataFrame of road segments for spatial operations
    seg_geoms = []
    seg_ids = []
    for seg in road_segments["segments"]:
        coords = [(c[0], c[1]) for c in seg["coords"]]
        if len(coords) >= 2:
            seg_geoms.append(LineString(coords))
            seg_ids.append(seg["id"])

    roads_gdf = gpd.GeoDataFrame(
        {"segment_id": seg_ids},
        geometry=seg_geoms,
        crs="EPSG:4326",
    )

    # Buffer roads slightly for intersection matching
    roads_proj = roads_gdf.to_crs(epsg=3857)
    roads_proj["geometry_buffered"] = roads_proj.geometry.buffer(30)  # 30m buffer
    roads_buffered = roads_proj.set_geometry("geometry_buffered")

    # Count trips per segment per time window
    # Initialize: segment_id -> [0, 0, 0, 0, 0] for 5 time windows
    segment_counts = defaultdict(lambda: [0] * len(TIME_WINDOWS))

    for trip_idx, trip_row in trip_geometries.iterrows():
        if trip_row.geometry is None or trip_row.geometry.is_empty:
            continue

        # Find which time window this trip falls in
        dep_sec = departure_seconds.iloc[trip_idx] if trip_idx < len(departure_seconds) else 3600
        window_idx = 0
        for i, tw in enumerate(TIME_WINDOWS):
            if tw["start"] <= dep_sec < tw["end"]:
                window_idx = i
                break

        # Project trip geometry for spatial operations
        trip_proj = gpd.GeoSeries([trip_row.geometry], crs="EPSG:4326").to_crs(epsg=3857).iloc[0]

        # Find intersecting road segments
        intersecting = roads_buffered[roads_buffered.geometry_buffered.intersects(trip_proj)]

        for _, seg_row in intersecting.iterrows():
            segment_counts[seg_row["segment_id"]][window_idx] += TRIP_SCALE_FACTOR

    print(f"    Assigned trips to {len(segment_counts)} road segments")
    return dict(segment_counts)


def compute_congestion_ratios(
    segment_counts: dict,
    road_segments: dict,
) -> dict:
    """
    Apply BPR formula to compute congestion ratio per segment per time window.

    Returns dict mapping segment_id -> list of 5 congestion ratios.
    Ratio of 1.0 = free flow, 1.5 = 50% slower, 2.0 = double the time.
    """
    print("  Computing BPR congestion ratios...")

    # Build lookup for road capacities
    capacity_lookup = {}
    for seg in road_segments["segments"]:
        # Capacity is per hour, time windows are 30 min -> divide by 2
        capacity_lookup[seg["id"]] = seg["capacity_per_hour"] / 2.0

    congestion_ratios = {}
    max_ratio = 0

    for seg_id, counts in segment_counts.items():
        capacity = capacity_lookup.get(seg_id, 900)  # Default 900 per 30 min
        ratios = []
        for volume in counts:
            if capacity > 0:
                vc_ratio = volume / capacity
                ratio = 1.0 + BPR_ALPHA * (vc_ratio ** BPR_BETA)
            else:
                ratio = 1.0
            # Cap at reasonable maximum (5x free flow)
            ratio = min(ratio, 5.0)
            ratios.append(round(ratio, 3))
            max_ratio = max(max_ratio, ratio)

        congestion_ratios[seg_id] = ratios

    # Also include segments with zero traffic (ratio = 1.0)
    for seg in road_segments["segments"]:
        if seg["id"] not in congestion_ratios:
            congestion_ratios[seg["id"]] = [1.0] * len(TIME_WINDOWS)

    print(f"    Max congestion ratio: {max_ratio:.2f}x free flow")
    print(f"    Segments with congestion > 1.2x: "
          f"{sum(1 for ratios in congestion_ratios.values() if max(ratios) > 1.2)}")

    return congestion_ratios


def adjust_car_travel_times(
    mode_choice_df: pd.DataFrame,
    congestion_ratios: dict,
    trip_segments: dict,
) -> pd.DataFrame:
    """
    Adjust car travel times using congestion ratios.
    Trips on congested roads get their car_minutes multiplied by the congestion ratio.

    Returns updated DataFrame with adjusted car_minutes and potentially different mode choices.
    """
    print("  Adjusting car travel times for congestion...")

    df = mode_choice_df.copy()

    # For a simplified approach: multiply car time by the average congestion ratio
    # of the segments the trip uses (approximation since we don't have per-trip segments
    # in the fast pass - we use a time-window average)
    if congestion_ratios:
        # Calculate average congestion ratio across peak windows (index 2-3 = 8:00-9:00)
        peak_ratios = []
        for seg_id, ratios in congestion_ratios.items():
            peak_avg = np.mean(ratios[2:4])  # 8:00-8:30 and 8:30-9:00
            peak_ratios.append(peak_avg)

        overall_avg = np.mean(peak_ratios) if peak_ratios else 1.0
        print(f"    Average peak congestion multiplier: {overall_avg:.2f}x")

        # Apply to car times
        df["car_minutes_congested"] = df["car_minutes"] * overall_avg

        # Recompute mode choice with congested car times
        def choose_mode_congested(row):
            times = {
                "CAR": row.get("car_minutes_congested", float("nan")),
                "TRANSIT": row.get("transit_minutes", float("nan")),
                "BICYCLE": row.get("bike_minutes", float("nan")),
            }
            valid = {k: v for k, v in times.items() if pd.notna(v)}
            if not valid:
                return "CAR"
            return min(valid, key=valid.get)

        df["chosen_mode_congested"] = df.apply(choose_mode_congested, axis=1)

        # Report shift
        original_car = (df["chosen_mode"] == "CAR").sum()
        congested_car = (df["chosen_mode_congested"] == "CAR").sum()
        shift = original_car - congested_car
        print(f"    Mode shift due to congestion: {shift} trips moved away from car")
        print(f"    Car share: {original_car/len(df)*100:.1f}% -> {congested_car/len(df)*100:.1f}%")

    return df


def export_congestion(
    scenario_name: str,
    congestion_ratios: dict,
):
    """Export congestion data as JSON for the visualization."""
    output = {
        "type": "congestion",
        "scenario": scenario_name,
        "time_windows": TIME_WINDOWS,
        "data": congestion_ratios,
    }

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORT_DIR / f"congestion_{scenario_name}.json"
    with open(out_path, "w") as f:
        json.dump(output, f)

    size_kb = out_path.stat().st_size / 1e3
    print(f"  Exported congestion data to {out_path} ({size_kb:.0f} KB)")

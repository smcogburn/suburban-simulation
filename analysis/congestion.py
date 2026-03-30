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
    MODE_CHOICE,
    TIME_WINDOWS,
    TRIP_SCALE_FACTOR,
    EXPORT_DIR,
)


def assign_trips_to_segments(
    trip_geometries: gpd.GeoDataFrame,
    road_segments: dict,
    departure_seconds: pd.Series,
    duration_seconds: pd.Series = None,
) -> dict:
    """
    Map each car trip to the road segments it traverses and count trips
    per segment per time window.

    Each trip is spread proportionally across all time windows it spans
    (departure → departure + duration), not just the departure window.
    This prevents the "spike at departure, nothing after" artifact.

    Args:
        trip_geometries: GeoDataFrame with trip LineString geometry
        road_segments: dict from roads.json (loaded road network)
        departure_seconds: Series of departure times (seconds since 7AM)
        duration_seconds: Series of trip durations in seconds (optional).
            If None, each trip is assumed to last one full window (1800s).

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
    segment_counts = defaultdict(lambda: [0.0] * len(TIME_WINDOWS))

    for trip_idx, trip_row in trip_geometries.iterrows():
        if trip_row.geometry is None or trip_row.geometry.is_empty:
            continue

        dep_sec = float(departure_seconds.iloc[trip_idx]) if trip_idx < len(departure_seconds) else 3600.0
        if duration_seconds is not None and trip_idx < len(duration_seconds):
            dur_sec = float(duration_seconds.iloc[trip_idx])
            # Guard against zero/NaN duration
            if not (dur_sec > 0):
                dur_sec = 1800.0
        else:
            dur_sec = 1800.0  # fallback: assume one full window

        arr_sec = dep_sec + dur_sec

        # Compute the fraction of this trip that falls in each time window
        window_weights = []
        for tw in TIME_WINDOWS:
            overlap = max(0.0, min(tw["end"], arr_sec) - max(tw["start"], dep_sec))
            window_weights.append(overlap / dur_sec)

        # Skip if trip doesn't overlap any window (shouldn't happen in normal data)
        if sum(window_weights) < 1e-6:
            continue

        # Project trip geometry for spatial operations
        trip_proj = gpd.GeoSeries([trip_row.geometry], crs="EPSG:4326").to_crs(epsg=3857).iloc[0]

        # Find intersecting road segments
        intersecting = roads_buffered[roads_buffered.geometry_buffered.intersects(trip_proj)]

        for _, seg_row in intersecting.iterrows():
            seg_id = seg_row["segment_id"]
            for wi, weight in enumerate(window_weights):
                if weight > 0:
                    segment_counts[seg_id][wi] += weight * TRIP_SCALE_FACTOR

    # Round counts to integers for BPR computation
    segment_counts = {
        seg_id: [round(c) for c in counts]
        for seg_id, counts in segment_counts.items()
    }

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
        # Capacity is per hour; scale to window duration
        window_hours = (TIME_WINDOWS[0]["end"] - TIME_WINDOWS[0]["start"]) / 3600.0
        capacity_lookup[seg["id"]] = seg["capacity_per_hour"] * window_hours

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
    Re-run mode choice using the actual BPR congestion ratio computed from real traffic counts.

    First-pass mode choice used car_bpr_factor=1.0 (free-flow). Now that we know the actual
    peak congestion ratio from the BPR model, we re-apply the generalized cost formula with
    the real congestion penalty. Same noise seed → reproducible, but some trips that barely
    chose CAR in free-flow will now flip to transit/bike.

    Returns updated DataFrame with chosen_mode updated in-place.
    """
    print("  Adjusting car travel times for congestion...")

    df = mode_choice_df.copy()

    if not congestion_ratios:
        return df

    # Compute the actual peak congestion ratio (average across peak windows 4-7 = 8:00-9:00)
    # Only use road segments that had any traffic (ratio > 1.0) to avoid diluting with empty roads
    peak_ratios = []
    for seg_id, ratios in congestion_ratios.items():
        peak_avg = np.mean(ratios[4:8])  # 8:00-8:15, 8:15-8:30, 8:30-8:45, 8:45-9:00
        if peak_avg > 1.0:
            peak_ratios.append(peak_avg)

    bpr_ratio = np.mean(peak_ratios) if peak_ratios else 1.0
    print(f"    Actual peak BPR congestion ratio: {bpr_ratio:.2f}x (from {len(peak_ratios)} congested segments)")

    df["car_minutes_congested"] = df["car_minutes"] * bpr_ratio

    # Re-run generalized cost mode choice with actual BPR ratio
    # Use same seed derivation as routing.py for consistent noise per OD pair
    def choose_mode_congested(row):
        seed = abs(hash(f"{row['from_id']}_{row['to_id']}")) % (2 ** 32)
        rng = np.random.default_rng(seed)
        noise = lambda: rng.normal(0, MODE_CHOICE["noise_std_min"])

        scores = {}
        car_min = row.get("car_minutes_congested")
        transit_min = row.get("transit_minutes")
        bike_min = row.get("bike_minutes")

        if pd.notna(car_min):
            scores["CAR"] = car_min * 1.0 + noise()  # BPR already applied to car_minutes_congested
        if pd.notna(transit_min):
            scores["TRANSIT"] = transit_min * MODE_CHOICE["transit_ivt_factor"] + noise()
        if pd.notna(bike_min):
            scores["BICYCLE"] = bike_min * MODE_CHOICE["bike_ivt_factor"] + noise()

        if not scores:
            return "CAR"
        return min(scores, key=scores.get)

    df["chosen_mode"] = df.apply(choose_mode_congested, axis=1)

    original_car = (mode_choice_df["chosen_mode"] == "CAR").sum()
    congested_car = (df["chosen_mode"] == "CAR").sum()
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

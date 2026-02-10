"""
Routing module: wraps r5py to compute travel times and detailed itineraries.

Uses a hybrid approach:
- TravelTimeMatrix for fast aggregate mode-share statistics (full OD matrix)
- DetailedItineraries for a subset of trips to get path geometry (3D visualization)
"""

import datetime
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
import r5py

from analysis.config import (
    DEPARTURE_DATE,
    DEPARTURE_SLOTS,
    GTFS_FEEDS,
    SCENARIOS,
)


def build_network(osm_pbf: Path, gtfs_dir: Path) -> r5py.TransportNetwork:
    """
    Build an r5py TransportNetwork from OSM and GTFS data.
    """
    # Collect GTFS files that exist in the directory
    gtfs_files = []
    for feed_name in GTFS_FEEDS:
        feed_path = gtfs_dir / feed_name
        if feed_path.exists():
            gtfs_files.append(str(feed_path))
            print(f"  GTFS: {feed_name}")
        else:
            print(f"  GTFS: {feed_name} (not found, skipping)")

    if not gtfs_files:
        print("  WARNING: No GTFS files found. Transit routing will not work.")

    print(f"  Building network from {osm_pbf.name} + {len(gtfs_files)} GTFS feeds...")

    network = r5py.TransportNetwork(
        str(osm_pbf),
        gtfs_files if gtfs_files else None,
    )

    print("  Network built successfully.")
    return network


def compute_travel_time_matrix(
    network: r5py.TransportNetwork,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    departure: datetime.datetime,
    modes: list,
) -> pd.DataFrame:
    """
    Compute a travel time matrix (fast, no path geometry).
    Returns DataFrame with from_id, to_id, travel_time columns.
    """
    ttm = r5py.TravelTimeMatrix(
        network,
        origins=origins,
        destinations=destinations,
        departure=departure,
        transport_modes=modes,
        snap_to_network=True,
    )
    return ttm


def compute_detailed_itineraries(
    network: r5py.TransportNetwork,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    departure: datetime.datetime,
    modes: list,
) -> gpd.GeoDataFrame:
    """
    Compute detailed itineraries (with path geometry, per-leg timing).
    Slower than TravelTimeMatrix — use only for the visualization subset.
    Returns GeoDataFrame with geometry, travel_time, transport_mode per leg.
    """
    itineraries = r5py.DetailedItineraries(
        network,
        origins=origins,
        destinations=destinations,
        departure=departure,
        transport_modes=modes,
        snap_to_network=True,
    )
    return itineraries


def run_scenario_fast(
    scenario_name: str,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
) -> dict:
    """
    Run TravelTimeMatrix for a scenario (fast pass — aggregate stats).
    Computes car and transit times separately, then determines mode choice.

    Returns dict with:
        - "car_times": DataFrame of car travel times
        - "transit_times": DataFrame of transit travel times
        - "bike_times": DataFrame of bike travel times (if applicable)
        - "mode_choice": DataFrame with chosen mode per OD pair
        - "stats": dict with mode share percentages
    """
    scenario = SCENARIOS[scenario_name]
    print(f"\n{'='*60}")
    print(f"Running scenario: {scenario['label']}")
    print(f"{'='*60}")

    # Build network
    network = build_network(scenario["osm_pbf"], scenario["gtfs_dir"])

    # Use the middle departure slot for the fast pass
    departure = datetime.datetime.combine(DEPARTURE_DATE, DEPARTURE_SLOTS[2])  # 8:00 AM
    print(f"  Departure time: {departure}")

    # --- Compute CAR travel times ---
    print("\n  Computing CAR travel times...")
    car_times = compute_travel_time_matrix(
        network, origins, destinations, departure,
        modes=[r5py.TransportMode.CAR],
    )
    car_times = car_times.rename(columns={"travel_time": "car_time"})
    # Convert timedelta to minutes
    car_times["car_minutes"] = car_times["car_time"].dt.total_seconds() / 60
    print(f"    Car trips computed: {len(car_times)}")

    # --- Compute TRANSIT + WALK travel times ---
    print("  Computing TRANSIT + WALK travel times...")
    transit_times = compute_travel_time_matrix(
        network, origins, destinations, departure,
        modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
    )
    transit_times = transit_times.rename(columns={"travel_time": "transit_time"})
    transit_times["transit_minutes"] = transit_times["transit_time"].dt.total_seconds() / 60
    print(f"    Transit trips computed: {len(transit_times)}")

    # --- Optionally compute BICYCLE travel times ---
    bike_times = None
    if scenario["include_bike"]:
        print("  Computing BICYCLE travel times...")
        bike_times = compute_travel_time_matrix(
            network, origins, destinations, departure,
            modes=[r5py.TransportMode.BICYCLE],
        )
        bike_times = bike_times.rename(columns={"travel_time": "bike_time"})
        bike_times["bike_minutes"] = bike_times["bike_time"].dt.total_seconds() / 60
        print(f"    Bike trips computed: {len(bike_times)}")

    # --- Merge and determine mode choice ---
    print("\n  Determining mode choice (fastest mode wins)...")
    merged = car_times[["from_id", "to_id", "car_minutes"]].merge(
        transit_times[["from_id", "to_id", "transit_minutes"]],
        on=["from_id", "to_id"],
        how="outer",
    )

    if bike_times is not None:
        merged = merged.merge(
            bike_times[["from_id", "to_id", "bike_minutes"]],
            on=["from_id", "to_id"],
            how="outer",
        )
    else:
        merged["bike_minutes"] = float("nan")

    # Choose fastest mode
    def choose_mode(row):
        times = {
            "CAR": row.get("car_minutes", float("nan")),
            "TRANSIT": row.get("transit_minutes", float("nan")),
            "BICYCLE": row.get("bike_minutes", float("nan")),
        }
        # Filter out NaN
        valid = {k: v for k, v in times.items() if pd.notna(v)}
        if not valid:
            return "CAR"  # Default if nothing computed
        return min(valid, key=valid.get)

    merged["chosen_mode"] = merged.apply(choose_mode, axis=1)
    merged["time_diff_transit_car"] = merged["transit_minutes"] - merged["car_minutes"]

    # Calculate stats
    mode_counts = merged["chosen_mode"].value_counts()
    total = len(merged)
    stats = {}
    for mode in ["CAR", "TRANSIT", "BICYCLE", "WALK"]:
        count = mode_counts.get(mode, 0)
        stats[f"{mode.lower()}_count"] = count
        stats[f"{mode.lower()}_pct"] = round(count / total * 100, 1) if total > 0 else 0
    stats["total_trips"] = total

    print(f"\n  Mode Share Results for {scenario['label']}:")
    print(f"  {'-'*40}")
    for mode in ["CAR", "TRANSIT", "BICYCLE"]:
        count = stats[f"{mode.lower()}_count"]
        pct = stats[f"{mode.lower()}_pct"]
        if count > 0:
            print(f"    {mode}: {count} trips ({pct}%)")
    print(f"    Total: {total} trips")

    return {
        "car_times": car_times,
        "transit_times": transit_times,
        "bike_times": bike_times,
        "mode_choice": merged,
        "stats": stats,
    }


def run_scenario_detailed(
    scenario_name: str,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
) -> dict:
    """
    Run DetailedItineraries for a scenario (slow pass — gets path geometry).
    Use only with the visualization subset (~500 OD pairs).

    Returns dict with:
        - "car_itineraries": GeoDataFrame with car route geometry
        - "transit_itineraries": GeoDataFrame with transit route geometry
        - "bike_itineraries": GeoDataFrame with bike route geometry (if applicable)
    """
    scenario = SCENARIOS[scenario_name]
    print(f"\n  Computing DetailedItineraries for viz subset ({scenario['label']})...")

    network = build_network(scenario["osm_pbf"], scenario["gtfs_dir"])
    departure = datetime.datetime.combine(DEPARTURE_DATE, DEPARTURE_SLOTS[2])  # 8:00 AM

    # Car itineraries
    print("    Car itineraries...")
    car_itin = compute_detailed_itineraries(
        network, origins, destinations, departure,
        modes=[r5py.TransportMode.CAR],
    )

    # Transit itineraries
    print("    Transit + Walk itineraries...")
    transit_itin = compute_detailed_itineraries(
        network, origins, destinations, departure,
        modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
    )

    # Bike itineraries (if applicable)
    bike_itin = None
    if scenario["include_bike"]:
        print("    Bicycle itineraries...")
        bike_itin = compute_detailed_itineraries(
            network, origins, destinations, departure,
            modes=[r5py.TransportMode.BICYCLE],
        )

    return {
        "car_itineraries": car_itin,
        "transit_itineraries": transit_itin,
        "bike_itineraries": bike_itin,
    }

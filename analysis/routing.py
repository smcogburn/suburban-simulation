"""
Routing module: wraps r5py to compute travel times and detailed itineraries.

Uses a hybrid approach:
- TravelTimeMatrix for fast aggregate mode-share statistics (full OD matrix)
- DetailedItineraries for a subset of trips to get path geometry (3D visualization)
"""

import datetime
import os
from pathlib import Path
from typing import Optional

# Cap the JVM heap before r5py starts it. Without this, the JVM will claim
# all available RAM + swap and freeze the machine during DetailedItineraries.
# Set to 10GB on a 16GB machine, leaving headroom for Python + OS.
if "JAVA_TOOL_OPTIONS" not in os.environ:
    os.environ["JAVA_TOOL_OPTIONS"] = "-Xmx10g"

import geopandas as gpd
import numpy as np
import pandas as pd
import r5py

from analysis.config import (
    DEPARTURE_DATE,
    DEPARTURE_SLOTS,
    GTFS_FEEDS,
    MODE_CHOICE,
    SCENARIOS,
    BIKE_MAX_LTS_BASELINE,
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

    if not osm_pbf.exists():
        raise FileNotFoundError(f"OSM PBF not found: {osm_pbf}")

    print(f"  Building network from {osm_pbf.name} + {len(gtfs_files)} GTFS feeds...")

    network = r5py.TransportNetwork(
        str(osm_pbf),
        gtfs_files,  # pass [] when empty, not None — r5py accepts empty list
    )

    print("  Network built successfully.")
    return network


def compute_travel_time_matrix(
    network: r5py.TransportNetwork,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    departure: datetime.datetime,
    modes: list,
    max_bicycle_traffic_stress: Optional[int] = None,
) -> pd.DataFrame:
    """
    Compute a travel time matrix (fast, no path geometry).
    Returns DataFrame with from_id, to_id, travel_time columns.
    """
    kwargs = {}
    if max_bicycle_traffic_stress is not None:
        kwargs["max_bicycle_traffic_stress"] = max_bicycle_traffic_stress
    ttm = r5py.TravelTimeMatrix(
        network,
        origins=origins,
        destinations=destinations,
        departure=departure,
        transport_modes=modes,
        snap_to_network=True,
        **kwargs,
    )
    return ttm


def compute_detailed_itineraries(
    network: r5py.TransportNetwork,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    departure: datetime.datetime,
    modes: list,
    max_bicycle_traffic_stress: Optional[int] = None,
) -> gpd.GeoDataFrame:
    """
    Compute detailed itineraries (with path geometry, per-leg timing).
    Slower than TravelTimeMatrix — use only for the visualization subset.
    Returns GeoDataFrame with geometry, travel_time, transport_mode per leg.
    """
    kwargs = {}
    if max_bicycle_traffic_stress is not None:
        kwargs["max_bicycle_traffic_stress"] = max_bicycle_traffic_stress
    itineraries = r5py.DetailedItineraries(
        network,
        origins=origins,
        destinations=destinations,
        departure=departure,
        transport_modes=modes,
        snap_to_network=True,
        **kwargs,
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
    # r5py 1.x returns travel_time as integer minutes already
    car_times["car_minutes"] = pd.to_numeric(car_times["car_time"], errors="coerce")
    print(f"    Car trips computed: {len(car_times)}")

    # --- Compute TRANSIT + WALK travel times ---
    print("  Computing TRANSIT + WALK travel times...")
    transit_times = compute_travel_time_matrix(
        network, origins, destinations, departure,
        modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
    )
    transit_times = transit_times.rename(columns={"travel_time": "transit_time"})
    transit_times["transit_minutes"] = pd.to_numeric(transit_times["transit_time"], errors="coerce")
    print(f"    Transit trips computed: {len(transit_times)}")

    # --- Optionally compute BICYCLE travel times ---
    bike_times = None
    if scenario["include_bike"]:
        # max_bicycle_traffic_stress=3 allows routing on LTS ≤ 3 roads (unprotected
        # arterials that real cyclists use). Policy B OSM tags protected lanes as LTS 2,
        # so those routes become faster/preferred automatically on the improved network.
        print("  Computing BICYCLE travel times (max LTS 3)...")
        bike_times = compute_travel_time_matrix(
            network, origins, destinations, departure,
            modes=[r5py.TransportMode.BICYCLE],
            max_bicycle_traffic_stress=BIKE_MAX_LTS_BASELINE,
        )
        bike_times = bike_times.rename(columns={"travel_time": "bike_time"})
        bike_times["bike_minutes"] = pd.to_numeric(bike_times["bike_time"], errors="coerce")
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

    # ── Diagnostics: print routing coverage and time gaps ──────────────────
    n_total = len(merged)
    n_transit_valid = merged["transit_minutes"].notna().sum()
    n_bike_valid    = merged["bike_minutes"].notna().sum() if "bike_minutes" in merged.columns else 0

    print(f"\n  Routing coverage ({n_total} OD pairs):")
    print(f"    Car valid:     {merged['car_minutes'].notna().sum()} ({100*merged['car_minutes'].notna().mean():.1f}%)")
    print(f"    Transit valid: {n_transit_valid} ({100*n_transit_valid/n_total:.1f}%)")
    if "bike_minutes" in merged.columns:
        print(f"    Bike valid:    {n_bike_valid} ({100*n_bike_valid/n_total:.1f}%)")

    if n_transit_valid > 0:
        gap = merged.loc[merged["transit_minutes"].notna(), "transit_minutes"] - \
              merged.loc[merged["transit_minutes"].notna(), "car_minutes"]
        print(f"\n  Transit vs car time gap (where both valid):")
        print(f"    mean={gap.mean():.1f} min  median={gap.median():.1f} min  "
              f"min={gap.min():.1f} min  max={gap.max():.1f} min")
        print(f"    Transit faster (gap<0):        {(gap < 0).sum()} pairs ({100*(gap<0).mean():.1f}%)")
        print(f"    Transit within 20 min of car:  {(gap < 20).sum()} pairs ({100*(gap<20).mean():.1f}%)")
        print(f"    Transit >40 min slower than car: {(gap > 40).sum()} pairs ({100*(gap>40).mean():.1f}%)")

    if n_bike_valid > 0 and "bike_minutes" in merged.columns:
        bgap = merged.loc[merged["bike_minutes"].notna(), "bike_minutes"] - \
               merged.loc[merged["bike_minutes"].notna(), "car_minutes"]
        print(f"\n  Bike vs car time gap (where both valid):")
        print(f"    mean={bgap.mean():.1f} min  median={bgap.median():.1f} min")
        print(f"    Bike faster (gap<0):           {(bgap < 0).sum()} pairs ({100*(bgap<0).mean():.1f}%)")
        print(f"    Bike within 10 min of car:     {(bgap < 10).sum()} pairs ({100*(bgap<10).mean():.1f}%)")
    # ── End diagnostics ─────────────────────────────────────────────────────

    # Generalized cost mode choice
    # score = travel_time * mode_factor + car_penalty + individual_noise
    # Lower score wins. Car penalty represents parking search + egress walk (8 min suburban
    # average). Without it, car is systematically under-priced vs transit/bike since car
    # travel times from r5py are pure in-vehicle time and exclude all access/egress costs.
    def choose_mode(row):
        seed = abs(hash(f"{row['from_id']}_{row['to_id']}")) % (2 ** 32)
        rng = np.random.default_rng(seed)
        noise = lambda: rng.normal(0, MODE_CHOICE["noise_std_min"])

        scores = {}
        car_min = row.get("car_minutes")
        transit_min = row.get("transit_minutes")
        bike_min = row.get("bike_minutes")

        if pd.notna(car_min):
            scores["CAR"] = car_min * MODE_CHOICE["car_bpr_factor"] + MODE_CHOICE["car_penalty_min"] + noise()
        if pd.notna(transit_min):
            scores["TRANSIT"] = transit_min * MODE_CHOICE["transit_ivt_factor"] + noise()
        if pd.notna(bike_min):
            scores["BICYCLE"] = bike_min * MODE_CHOICE["bike_ivt_factor"] + noise()

        if not scores:
            return "CAR"
        return min(scores, key=scores.get)

    merged["chosen_mode"] = merged.apply(choose_mode, axis=1)
    merged["time_diff_transit_car"] = merged["transit_minutes"] - merged["car_minutes"]

    # Post-choice diagnostics: how many chose each mode before final tally
    pre_tally = merged["chosen_mode"].value_counts()
    print(f"\n  Pre-BPR mode choice (before congestion adjustment):")
    for mode in ["CAR", "TRANSIT", "BICYCLE"]:
        c = pre_tally.get(mode, 0)
        print(f"    {mode}: {c} ({100*c/n_total:.1f}%)")

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
        "network": network,  # reuse in detailed pass to avoid rebuilding
    }


def run_scenario_detailed(
    scenario_name: str,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    network=None,
) -> dict:
    """
    Run DetailedItineraries for a scenario (slow pass — gets path geometry).
    Use only with the visualization subset (~500 OD pairs).

    Pass `network` from run_scenario_fast() to avoid rebuilding it a second time.

    Returns dict with:
        - "car_itineraries": GeoDataFrame with car route geometry
        - "transit_itineraries": GeoDataFrame with transit route geometry
        - "bike_itineraries": GeoDataFrame with bike route geometry (if applicable)
    """
    scenario = SCENARIOS[scenario_name]
    print(f"\n  Computing DetailedItineraries for viz subset ({scenario['label']})...")

    if network is None:
        network = build_network(scenario["osm_pbf"], scenario["gtfs_dir"])
    else:
        print("  Reusing network from fast pass (skipping rebuild).")
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
        print("    Bicycle itineraries (max LTS 3)...")
        bike_itin = compute_detailed_itineraries(
            network, origins, destinations, departure,
            modes=[r5py.TransportMode.BICYCLE],
            max_bicycle_traffic_stress=BIKE_MAX_LTS_BASELINE,
        )

    return {
        "car_itineraries": car_itin,
        "transit_itineraries": transit_itin,
        "bike_itineraries": bike_itin,
    }

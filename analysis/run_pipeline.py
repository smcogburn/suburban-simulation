"""
Master pipeline script: runs the full analysis for all 4 scenarios.

Usage:
    python -m analysis.run_pipeline                    # Run everything
    python -m analysis.run_pipeline --scenario baseline # Run one scenario
    python -m analysis.run_pipeline --skip-detailed    # Skip slow DetailedItineraries
    python -m analysis.run_pipeline --prep-only        # Just data prep, no routing
"""

import argparse
import json
import sys
import time

from analysis.config import SCENARIOS, EXPORT_DIR, TIME_WINDOWS
from analysis.data_prep import extract_buildings, extract_roads
from analysis.od_generation import (
    get_residential_origins,
    get_destinations,
    create_od_matrix,
    select_viz_subset,
)
from analysis.routing import run_scenario_fast, run_scenario_detailed
from analysis.congestion import (
    assign_trips_to_segments,
    compute_congestion_ratios,
    adjust_car_travel_times,
    export_congestion,
)
from analysis.exporter import export_trips, export_metadata


def run_pipeline(
    scenarios: list = None,
    skip_detailed: bool = False,
    prep_only: bool = False,
    force_prep: bool = False,
    diag_only: bool = False,
):
    """Run the full analysis pipeline."""
    start_time = time.time()

    if scenarios is None:
        scenarios = list(SCENARIOS.keys())

    print("=" * 60)
    print("SUBURBAN SIMULATION - ANALYSIS PIPELINE")
    print("=" * 60)
    print(f"Scenarios to run: {scenarios}")
    print(f"Skip DetailedItineraries: {skip_detailed}")
    if diag_only:
        print("DIAG MODE: Will stop after fast-pass routing diagnostics (no exports)")
    print()

    # ─── Step 1: Extract buildings and roads for visualization ───
    buildings_json_path = EXPORT_DIR / "buildings.json"
    roads_json_path = EXPORT_DIR / "roads.json"
    files_exist = buildings_json_path.exists() and roads_json_path.exists()

    print("\n" + "=" * 60)
    print("STEP 1: Buildings and roads")
    print("=" * 60)
    if files_exist and not force_prep:
        print(f"  buildings.json and roads.json already exist — skipping extraction.")
        print(f"  (Run with --force-prep to re-extract.)")
        buildings = None  # not needed downstream
    else:
        buildings = extract_buildings()
        roads_data = extract_roads()

    # Load roads.json for congestion analysis
    with open(roads_json_path, "r") as f:
        roads_json = json.load(f)

    if prep_only:
        print("\n--prep-only flag set, stopping after data preparation.")
        return

    # ─── Step 2: Generate OD pairs ───
    print("\n" + "=" * 60)
    print("STEP 2: Generating origin-destination pairs")
    print("=" * 60)
    origins = get_residential_origins()
    destinations = get_destinations()
    od_matrix = create_od_matrix(origins, destinations)
    viz_subset = select_viz_subset(od_matrix)

    # Convert origins/destinations to GeoDataFrames that r5py expects
    # (need 'id' column and geometry)
    import geopandas as gpd
    origins_gdf = gpd.GeoDataFrame(origins, geometry="geometry", crs="EPSG:4326")
    destinations_gdf = gpd.GeoDataFrame(destinations, geometry="geometry", crs="EPSG:4326")

    # ─── Step 3: Run scenarios ───
    all_stats = {}

    for scenario_name in scenarios:
        print("\n" + "=" * 60)
        print(f"STEP 3: Running scenario: {scenario_name}")
        print("=" * 60)

        # Check that the scenario's required files exist before trying to run
        scenario_cfg = SCENARIOS[scenario_name]
        osm_pbf = scenario_cfg["osm_pbf"]
        gtfs_dir = scenario_cfg["gtfs_dir"]
        if not osm_pbf.exists():
            print(f"  SKIPPING: OSM PBF not found at {osm_pbf}")
            print(f"  Run scenario_builder.py (Policy B) to create it.")
            continue
        if not gtfs_dir.exists() or not any(gtfs_dir.iterdir()):
            print(f"  SKIPPING: GTFS directory empty or missing: {gtfs_dir}")
            print(f"  Run scenario_builder.py (Policy A) to create doubled GTFS.")
            continue

        # Fast pass: TravelTimeMatrix for mode-share statistics
        fast_results = run_scenario_fast(scenario_name, origins_gdf, destinations_gdf)
        all_stats[scenario_name] = fast_results["stats"]

        if diag_only:
            print(f"\n  [--diag-only] Stopping after fast pass for {scenario_name}. No exports written.")
            continue

        # Congestion analysis (using the fast-pass mode choice data)
        print(f"\n  Running congestion analysis for {scenario_name}...")

        # For congestion, we need trip geometries. In the fast pass we only have
        # travel times, not geometry. We'll use a simplified approach:
        # assign congestion based on which road segments connect each OD pair.
        # The detailed pass (if run) will give us actual geometries.

        if not skip_detailed:
            # Slow pass: DetailedItineraries for a small fixed origin sample.
            #
            # IMPORTANT: r5py DetailedItineraries computes ALL M×N pairs.
            # Passing 500 unique origins × 30 destinations = 15,000 routes × 3 modes
            # = 45,000 geometry objects → fills all RAM and crashes.
            #
            # Instead: sample VIZ_DET_ORIGINS origins, route to ALL destinations.
            # 20 × 30 = 600 pairs per mode — large enough for a good visualization,
            # small enough to fit in memory.
            import numpy as np
            VIZ_DET_ORIGINS = 20
            rng_det = np.random.default_rng(42)
            det_ids = rng_det.choice(
                origins_gdf["id"].values,
                size=min(VIZ_DET_ORIGINS, len(origins_gdf)),
                replace=False,
            )
            viz_origins = origins_gdf[origins_gdf["id"].isin(det_ids)]
            viz_destinations = destinations_gdf  # all destinations

            print(f"\n  Running DetailedItineraries for {len(viz_origins)} origins × "
                  f"{len(viz_destinations)} destinations = "
                  f"{len(viz_origins) * len(viz_destinations)} pairs per mode...")

            detailed_results = run_scenario_detailed(
                scenario_name, viz_origins, viz_destinations,
                network=fast_results.get("network"),
            )

            # Compute congestion from car itineraries
            car_itin = detailed_results["car_itineraries"]
            if car_itin is not None and len(car_itin) > 0:
                car_geoms = car_itin[car_itin.geometry.notna()]
                if len(car_geoms) > 0:
                    # Look up departure seconds from full od_matrix (not viz_subset,
                    # since detailed origins may differ from viz_subset origins)
                    dep_lookup = od_matrix.set_index(["from_id", "to_id"])["departure_seconds"]
                    dep_sec_series = car_geoms.apply(
                        lambda row: dep_lookup.get((row["from_id"], row["to_id"]), 3600),
                        axis=1,
                    )

                    # Extract trip durations (travel_time is timedelta in DetailedItineraries)
                    if "travel_time" in car_geoms.columns:
                        dur_sec_series = car_geoms["travel_time"].dt.total_seconds()
                    else:
                        dur_sec_series = None

                    segment_counts = assign_trips_to_segments(
                        car_geoms, roads_json, dep_sec_series, dur_sec_series
                    )
                    congestion_ratios = compute_congestion_ratios(segment_counts, roads_json)
                else:
                    congestion_ratios = {}
            else:
                congestion_ratios = {}

            # Export congestion
            export_congestion(scenario_name, congestion_ratios)

            # Adjust car times and recompute mode choice
            if congestion_ratios:
                adjusted_df = adjust_car_travel_times(
                    fast_results["mode_choice"], congestion_ratios, {}
                )
            else:
                adjusted_df = fast_results["mode_choice"]

            # Export trips for visualization
            # Add departure_seconds to the mode choice df
            merged_with_dep = adjusted_df.merge(
                od_matrix[["from_id", "to_id", "departure_seconds"]],
                on=["from_id", "to_id"],
                how="left",
            )
            merged_with_dep["departure_seconds"] = merged_with_dep["departure_seconds"].fillna(3600)

            export_trips(
                scenario_name,
                merged_with_dep,
                detailed_results["car_itineraries"],
                detailed_results["transit_itineraries"],
                detailed_results.get("bike_itineraries"),
                roads_json,
            )
        else:
            # Export empty congestion (all free-flow)
            congestion_ratios = {
                seg["id"]: [1.0] * len(TIME_WINDOWS) for seg in roads_json["segments"]
            }
            export_congestion(scenario_name, congestion_ratios)

    # ─── Step 4: Export metadata ───
    print("\n" + "=" * 60)
    print("STEP 4: Exporting metadata")
    print("=" * 60)
    export_metadata(all_stats)

    # ─── Done ───
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"PIPELINE COMPLETE in {elapsed/60:.1f} minutes")
    print("=" * 60)
    print(f"\nExported files in {EXPORT_DIR}:")
    for f in sorted(EXPORT_DIR.glob("*.json")):
        size = f.stat().st_size / 1e3
        print(f"  {f.name} ({size:.0f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Run suburban simulation analysis pipeline")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()),
                        help="Run only one scenario")
    parser.add_argument("--skip-detailed", action="store_true",
                        help="Skip DetailedItineraries (faster, no viz paths)")
    parser.add_argument("--prep-only", action="store_true",
                        help="Only run data preparation, no routing")
    parser.add_argument("--force-prep", action="store_true",
                        help="Re-extract buildings/roads even if files already exist")
    parser.add_argument("--diag-only", action="store_true",
                        help="Run fast-pass routing and print diagnostics only — no DetailedItineraries, no exports. "
                             "Use to quickly validate transit/bike coverage and time gaps.")
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario else None
    run_pipeline(
        scenarios=scenarios,
        skip_detailed=args.skip_detailed,
        prep_only=args.prep_only,
        force_prep=args.force_prep,
        diag_only=args.diag_only,
    )


if __name__ == "__main__":
    main()

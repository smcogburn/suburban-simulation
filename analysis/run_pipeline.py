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

from analysis.config import SCENARIOS, EXPORT_DIR
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
    print()

    # ─── Step 1: Extract buildings and roads for visualization ───
    print("\n" + "=" * 60)
    print("STEP 1: Extracting buildings and roads")
    print("=" * 60)
    buildings = extract_buildings()
    roads_data = extract_roads()

    # Load roads.json for congestion analysis
    roads_json_path = EXPORT_DIR / "roads.json"
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

        # Fast pass: TravelTimeMatrix for mode-share statistics
        fast_results = run_scenario_fast(scenario_name, origins_gdf, destinations_gdf)
        all_stats[scenario_name] = fast_results["stats"]

        # Congestion analysis (using the fast-pass mode choice data)
        print(f"\n  Running congestion analysis for {scenario_name}...")

        # For congestion, we need trip geometries. In the fast pass we only have
        # travel times, not geometry. We'll use a simplified approach:
        # assign congestion based on which road segments connect each OD pair.
        # The detailed pass (if run) will give us actual geometries.

        if not skip_detailed:
            # Slow pass: DetailedItineraries for viz subset
            print(f"\n  Running DetailedItineraries for viz subset...")

            # Create subset GeoDataFrames
            viz_from_ids = viz_subset["from_id"].unique()
            viz_to_ids = viz_subset["to_id"].unique()
            viz_origins = origins_gdf[origins_gdf["id"].isin(viz_from_ids)]
            viz_destinations = destinations_gdf[destinations_gdf["id"].isin(viz_to_ids)]

            detailed_results = run_scenario_detailed(
                scenario_name, viz_origins, viz_destinations
            )

            # Compute congestion from car itineraries
            car_itin = detailed_results["car_itineraries"]
            if car_itin is not None and len(car_itin) > 0:
                car_geoms = car_itin[car_itin.geometry.notna()]
                if len(car_geoms) > 0:
                    dep_seconds = viz_subset.set_index(["from_id", "to_id"])
                    # Create departure_seconds series aligned with car_geoms
                    dep_sec_series = car_geoms.apply(
                        lambda row: dep_seconds.loc[
                            (row["from_id"], row["to_id"]), "departure_seconds"
                        ] if (row["from_id"], row["to_id"]) in dep_seconds.index else 3600,
                        axis=1,
                    )

                    segment_counts = assign_trips_to_segments(
                        car_geoms, roads_json, dep_sec_series
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
                viz_subset[["from_id", "to_id", "departure_seconds"]],
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
                seg["id"]: [1.0] * 5 for seg in roads_json["segments"]
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
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario else None
    run_pipeline(
        scenarios=scenarios,
        skip_detailed=args.skip_detailed,
        prep_only=args.prep_only,
    )


if __name__ == "__main__":
    main()

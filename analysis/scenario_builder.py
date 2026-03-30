"""
Scenario builder: modify GTFS and OSM data for policy interventions.

Policy A: Double bus frequency by inserting interpolated trips in GTFS feeds.
Policy B: Add protected bike lanes by modifying LTS values in OSM data.
"""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from analysis.config import (
    GTFS_BASELINE_DIR,
    GTFS_DOUBLED_DIR,
    GTFS_FEEDS,
    OSM_PBF_STUDY,
    OSM_PBF_BIKE,
    BIKE_LANE_HIGHWAY_TYPES,
)


def double_bus_frequency():
    """
    Policy A: Double bus frequency by inserting interpolated trips.

    For each route operating during morning rush (7:00-9:30 AM),
    insert new trips at the midpoint between consecutive existing trips.
    This effectively halves headways.

    Focus on the local bus feed (most relevant to suburban Columbia).
    """
    print("\n" + "=" * 60)
    print("POLICY A: Doubling bus frequency")
    print("=" * 60)

    GTFS_DOUBLED_DIR.mkdir(parents=True, exist_ok=True)

    for feed_name in GTFS_FEEDS:
        baseline_path = GTFS_BASELINE_DIR / feed_name
        doubled_path = GTFS_DOUBLED_DIR / feed_name

        if not baseline_path.exists():
            print(f"  Skipping {feed_name} (not found)")
            continue

        # Only modify local bus - copy others unchanged
        if "localbus" not in feed_name:
            shutil.copy2(baseline_path, doubled_path)
            print(f"  Copied {feed_name} unchanged")
            continue

        print(f"  Modifying {feed_name}...")
        _double_feed_frequency(baseline_path, doubled_path)


def _double_feed_frequency(input_zip: Path, output_zip: Path):
    """
    Read a GTFS zip, double the trip frequency during morning rush, write new zip.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract the GTFS zip
        with zipfile.ZipFile(input_zip, "r") as z:
            z.extractall(tmpdir)

        # Read key files
        trips_path = os.path.join(tmpdir, "trips.txt")
        stop_times_path = os.path.join(tmpdir, "stop_times.txt")

        if not os.path.exists(trips_path) or not os.path.exists(stop_times_path):
            print("    Warning: trips.txt or stop_times.txt not found, copying unchanged")
            shutil.copy2(input_zip, output_zip)
            return

        trips_df = pd.read_csv(trips_path, dtype=str)
        stop_times_df = pd.read_csv(stop_times_path, dtype=str)

        print(f"    Original trips: {len(trips_df)}")
        print(f"    Original stop_times: {len(stop_times_df)}")

        # Parse departure times to seconds for comparison
        def time_to_seconds(t):
            """Convert HH:MM:SS to seconds since midnight."""
            try:
                parts = str(t).split(":")
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (ValueError, IndexError):
                return None

        def seconds_to_time(s):
            """Convert seconds since midnight to HH:MM:SS."""
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = int(s % 60)
            return f"{h:02d}:{m:02d}:{sec:02d}"

        # Get first departure time for each trip
        first_stops = stop_times_df.groupby("trip_id").first().reset_index()
        first_stops["dep_seconds"] = first_stops["departure_time"].apply(time_to_seconds)

        # Filter to morning rush trips (7:00 AM - 9:30 AM = 25200 - 34200 seconds)
        rush_start = 7 * 3600   # 25200
        rush_end = 9.5 * 3600   # 34200

        rush_trips = first_stops[
            (first_stops["dep_seconds"] >= rush_start) &
            (first_stops["dep_seconds"] <= rush_end)
        ]["trip_id"].tolist()

        print(f"    Morning rush trips (7:00-9:30): {len(rush_trips)}")

        # Group rush trips by route_id and direction_id
        rush_trip_info = trips_df[trips_df["trip_id"].isin(rush_trips)].copy()

        new_trips = []
        new_stop_times = []
        interp_count = 0

        for (route_id, direction), group in rush_trip_info.groupby(
            ["route_id", "direction_id"]
        ):
            # Get departure times for trips on this route/direction
            trip_dep_times = []
            for _, trip_row in group.iterrows():
                trip_id = trip_row["trip_id"]
                first_stop = first_stops[first_stops["trip_id"] == trip_id]
                if len(first_stop) > 0:
                    dep_sec = first_stop.iloc[0]["dep_seconds"]
                    if dep_sec is not None:
                        trip_dep_times.append((trip_id, dep_sec))

            # Sort by departure time
            trip_dep_times.sort(key=lambda x: x[1])

            TARGET_HEADWAY = 300  # 5 minutes in seconds

            # Insert trips every 5 minutes throughout each gap
            for i in range(len(trip_dep_times) - 1):
                trip_a_id, dep_a = trip_dep_times[i]
                trip_b_id, dep_b = trip_dep_times[i + 1]

                headway = dep_b - dep_a
                if headway <= TARGET_HEADWAY:  # Already at or below 5-min headway
                    continue

                # Get stop pattern from trip A (reused for all inserts in this gap)
                trip_a_stops = stop_times_df[
                    stop_times_df["trip_id"] == trip_a_id
                ].copy()

                if len(trip_a_stops) == 0:
                    continue

                trip_a_row = trips_df[trips_df["trip_id"] == trip_a_id].iloc[0].copy()

                # Insert as many trips as needed to reach 5-min headways
                num_inserts = headway // TARGET_HEADWAY - 1
                for j in range(1, num_inserts + 1):
                    offset = j * TARGET_HEADWAY
                    new_trip_id = f"{trip_a_id}_5min_{i}_{j}"

                    new_trip = trip_a_row.copy()
                    new_trip["trip_id"] = new_trip_id
                    new_trips.append(new_trip)

                    for _, stop_row in trip_a_stops.iterrows():
                        new_stop = stop_row.copy()
                        new_stop["trip_id"] = new_trip_id

                        arr_sec = time_to_seconds(stop_row["arrival_time"])
                        dep_sec = time_to_seconds(stop_row["departure_time"])

                        if arr_sec is not None:
                            new_stop["arrival_time"] = seconds_to_time(arr_sec + offset)
                        if dep_sec is not None:
                            new_stop["departure_time"] = seconds_to_time(dep_sec + offset)

                        new_stop_times.append(new_stop)

                    interp_count += 1

        # Append new data
        if new_trips:
            new_trips_df = pd.DataFrame(new_trips)
            trips_df = pd.concat([trips_df, new_trips_df], ignore_index=True)

        if new_stop_times:
            new_st_df = pd.DataFrame(new_stop_times)
            stop_times_df = pd.concat([stop_times_df, new_st_df], ignore_index=True)

        print(f"    Interpolated trips added: {interp_count}")
        print(f"    New total trips: {len(trips_df)}")
        print(f"    New total stop_times: {len(stop_times_df)}")

        # Write modified files back
        trips_df.to_csv(trips_path, index=False)
        stop_times_df.to_csv(stop_times_path, index=False)

        # Re-zip
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, tmpdir)
                    zout.write(file_path, arcname)

        size_mb = output_zip.stat().st_size / 1e6
        print(f"    Written to {output_zip} ({size_mb:.1f} MB)")


def add_bike_lanes():
    """
    Policy B: Add protected bike lanes to arterial roads.

    Modifies the OSM PBF to set LTS=2 on primary, secondary, and tertiary roads,
    simulating the addition of protected cycling infrastructure.

    Requires pyosmium.
    """
    print("\n" + "=" * 60)
    print("POLICY B: Adding protected bike lanes")
    print("=" * 60)

    if not OSM_PBF_STUDY.exists():
        print(f"  ERROR: Study area PBF not found at {OSM_PBF_STUDY}")
        print("  Run data_prep.py first to clip the OSM data.")
        return

    try:
        import osmium
    except ImportError:
        print("  ERROR: pyosmium not installed. Install with: pip install pyosmium")
        return

    print(f"  Input: {OSM_PBF_STUDY}")
    print(f"  Modifying roads with highway types: {BIKE_LANE_HIGHWAY_TYPES}")

    class BikeLaneHandler(osmium.SimpleHandler):
        """Handler that adds bike lane tags to arterial roads."""

        def __init__(self, writer):
            super().__init__()
            self.writer = writer
            self.modified_count = 0

        def node(self, n):
            self.writer.add_node(n)

        def way(self, w):
            highway = w.tags.get("highway", "")
            if highway in BIKE_LANE_HIGHWAY_TYPES:
                # Add bike lane tags
                new_tags = dict(w.tags)
                new_tags["cycleway"] = "lane"
                new_tags["lts"] = "2"
                self.writer.add_way(
                    w.replace(tags=new_tags)
                )
                self.modified_count += 1
            else:
                self.writer.add_way(w)

        def relation(self, r):
            self.writer.add_relation(r)

    writer = osmium.SimpleWriter(str(OSM_PBF_BIKE), overwrite=True)
    handler = BikeLaneHandler(writer)
    handler.apply_file(str(OSM_PBF_STUDY))
    writer.close()

    size_mb = OSM_PBF_BIKE.stat().st_size / 1e6
    print(f"  Modified {handler.modified_count} road segments")
    print(f"  Written to {OSM_PBF_BIKE} ({size_mb:.1f} MB)")


def build_all_scenarios():
    """Build modified data for all policy scenarios."""
    double_bus_frequency()
    add_bike_lanes()
    print("\nAll scenario data prepared.")


if __name__ == "__main__":
    build_all_scenarios()

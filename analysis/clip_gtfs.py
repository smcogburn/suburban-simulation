"""
Clip GTFS feeds to only stops/trips within the study area bounding box.

Dramatically reduces transit routing time by discarding stops in
Largo, Upper Marlboro, and other areas outside the Bowie/Annapolis corridor.

Run once before the pipeline:
    python -m analysis.clip_gtfs
"""

import zipfile
import io
import os
from pathlib import Path

import pandas as pd

from analysis.config import GTFS_BASELINE_DIR, ANALYSIS_BBOX

# Expand bbox by a small buffer so routes entering the area are included
BUFFER = 0.05  # ~5km in degrees


def clip_gtfs_feed(feed_path: Path, out_path: Path):
    """
    Clip a GTFS zip to stops within ANALYSIS_BBOX + buffer.
    Filters: stops → trips (touching bbox) → stop_times → routes → shapes.
    Writes the clipped zip to out_path.
    """
    print(f"  Clipping {feed_path.name}...")

    bbox = ANALYSIS_BBOX
    west  = bbox["west"]  - BUFFER
    east  = bbox["east"]  + BUFFER
    south = bbox["south"] - BUFFER
    north = bbox["north"] + BUFFER

    with zipfile.ZipFile(feed_path) as zf:
        files = {name: zf.read(name) for name in zf.namelist()}

    def read_csv(name):
        if name not in files:
            return None
        return pd.read_csv(io.BytesIO(files[name]), dtype=str, low_memory=False)

    stops_df      = read_csv("stops.txt")
    trips_df      = read_csv("trips.txt")
    stop_times_df = read_csv("stop_times.txt")
    routes_df     = read_csv("routes.txt")
    shapes_df     = read_csv("shapes.txt")

    if stops_df is None or trips_df is None or stop_times_df is None:
        print(f"    Missing required tables — copying unchanged")
        import shutil
        shutil.copy2(feed_path, out_path)
        return

    original_stops = len(stops_df)
    original_trips = len(trips_df)
    original_st    = len(stop_times_df)

    # 1. Filter stops to bbox
    stops_df["stop_lat"] = pd.to_numeric(stops_df["stop_lat"], errors="coerce")
    stops_df["stop_lon"] = pd.to_numeric(stops_df["stop_lon"], errors="coerce")
    in_bbox = (
        (stops_df["stop_lat"] >= south) & (stops_df["stop_lat"] <= north) &
        (stops_df["stop_lon"] >= west)  & (stops_df["stop_lon"] <= east)
    )
    stops_in_bbox = set(stops_df.loc[in_bbox, "stop_id"])

    if not stops_in_bbox:
        print(f"    No stops in bbox — skipping this feed")
        return

    # 2. Filter trips to those touching bbox (have at least one stop in bbox)
    st_in_bbox = stop_times_df[stop_times_df["stop_id"].isin(stops_in_bbox)]
    trips_in_bbox = set(st_in_bbox["trip_id"])

    # 3. Filter stop_times to bbox trips
    stop_times_filtered = stop_times_df[stop_times_df["trip_id"].isin(trips_in_bbox)]

    # 4. Filter trips
    trips_filtered = trips_df[trips_df["trip_id"].isin(trips_in_bbox)]

    # 5. All stops referenced by filtered stop_times (include stops outside bbox
    #    but on routes that pass through — needed for correct routing)
    all_stops_used = set(stop_times_filtered["stop_id"])
    stops_filtered = stops_df[stops_df["stop_id"].isin(all_stops_used)]

    # 6. Filter routes to used routes
    if routes_df is not None:
        used_routes = set(trips_filtered["route_id"])
        routes_filtered = routes_df[routes_df["route_id"].isin(used_routes)]
    else:
        routes_filtered = None

    # 7. Filter shapes (if present and non-empty)
    if shapes_df is not None and len(shapes_df) > 0 and "shape_id" in trips_filtered.columns:
        used_shapes = set(trips_filtered["shape_id"].dropna())
        shapes_filtered = shapes_df[shapes_df["shape_id"].isin(used_shapes)]
    else:
        shapes_filtered = shapes_df  # keep as-is (may be None or empty)

    # Build filtered zip
    kept = {}
    for name, data in files.items():
        if name == "stops.txt":
            kept[name] = stops_filtered.to_csv(index=False).encode("utf-8")
        elif name == "trips.txt":
            kept[name] = trips_filtered.to_csv(index=False).encode("utf-8")
        elif name == "stop_times.txt":
            kept[name] = stop_times_filtered.to_csv(index=False).encode("utf-8")
        elif name == "routes.txt" and routes_filtered is not None:
            kept[name] = routes_filtered.to_csv(index=False).encode("utf-8")
        elif name == "shapes.txt" and shapes_filtered is not None:
            kept[name] = shapes_filtered.to_csv(index=False).encode("utf-8")
        else:
            kept[name] = data  # calendar, agency, feed_info etc — keep unchanged

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(out_path) + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in kept.items():
            zf.writestr(name, data)
    os.replace(tmp, out_path)

    print(f"    Stops:      {original_stops:,} → {len(stops_filtered):,}")
    print(f"    Trips:      {original_trips:,} → {len(trips_filtered):,}")
    print(f"    Stop-times: {original_st:,} → {len(stop_times_filtered):,}")


def clip_all_feeds():
    """
    Clip AAC and PG County feeds in-place (overwrite baseline copies).
    Other feeds (MTA regional) are already scoped and don't need clipping.
    """
    FEEDS_TO_CLIP = [
        "aac_gtfs.zip",
        "princegeorgescounty-md-us.zip",
    ]

    print("Clipping GTFS feeds to study bbox...")
    print(f"  Bbox: W={ANALYSIS_BBOX['west']}, S={ANALYSIS_BBOX['south']}, "
          f"E={ANALYSIS_BBOX['east']}, N={ANALYSIS_BBOX['north']} (±{BUFFER}° buffer)")
    print()

    for feed_name in FEEDS_TO_CLIP:
        feed_path = GTFS_BASELINE_DIR / feed_name
        if not feed_path.exists():
            print(f"  Skipping {feed_name} (not found)")
            continue
        clip_gtfs_feed(feed_path, feed_path)  # overwrite in place

    print()
    print("Done. Also clearing r5py cache so it rebuilds with clipped feeds.")
    import glob
    cache_dir = Path.home() / "AppData" / "Local" / "r5py"
    for f in cache_dir.glob("*.transport_network"):
        f.unlink()
    for f in cache_dir.glob("*.mapdb"):
        f.unlink()
    for f in cache_dir.glob("*.mapdb.p"):
        f.unlink()
    # Update cached copies
    for feed_name in FEEDS_TO_CLIP:
        src = GTFS_BASELINE_DIR / feed_name
        dst = cache_dir / feed_name
        if src.exists() and dst.exists():
            import shutil
            shutil.copy2(src, dst)
            print(f"  Updated r5py cache: {feed_name}")

    print("\nRun the pipeline normally — transit routing will be much faster.")


if __name__ == "__main__":
    clip_all_feeds()

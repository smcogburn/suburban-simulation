"""
Data preparation: clip OSM data, extract buildings and roads for visualization.

Uses osmnx (Overpass API) for building/road extraction — works on Windows without pyrosm.

Usage:
    python -m analysis.data_prep              # Run all prep steps
    python -m analysis.data_prep --step clip  # Just clip OSM (needs osmium-tool)
    python -m analysis.data_prep --step extract  # Extract buildings/roads (needs internet)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd

# Cache to system temp (not OneDrive) to avoid sync/space issues
ox.settings.cache_folder = str(Path(tempfile.gettempdir()) / "osmnx_cache")
ox.settings.use_cache = True
# Raise the per-request area limit so the entire VIZ_BBOX downloads in 1-2 requests
# (default is tiny, causing ~39,000 sub-requests and many minutes of wait)
ox.settings.max_query_area_size = 50_000_000  # 50 km²

from analysis.config import (
    ANALYSIS_BBOX,
    VIZ_BBOX,
    OSM_DIR,
    OSM_PBF_FULL,
    OSM_PBF_STUDY,
    EXPORT_DIR,
    DEFAULT_LANES,
    CAPACITY_PER_LANE,
)


def clip_osm_to_study_area():
    """
    Clip the full Maryland OSM PBF to the analysis bounding box using osmium.
    Requires: sudo apt install osmium-tool (Linux/WSL)
    """
    if not OSM_PBF_FULL.exists():
        print(f"ERROR: Maryland PBF not found at {OSM_PBF_FULL}")
        print("Download from: https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf")
        sys.exit(1)

    bbox = ANALYSIS_BBOX
    bbox_str = f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"

    print(f"Clipping OSM PBF to bounding box: {bbox_str}")
    print(f"  Input:  {OSM_PBF_FULL} ({OSM_PBF_FULL.stat().st_size / 1e6:.1f} MB)")

    result = subprocess.run(
        ["osmium", "extract", "-b", bbox_str, str(OSM_PBF_FULL),
         "-o", str(OSM_PBF_STUDY), "--overwrite"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: osmium extract failed:\n{result.stderr}")
        print("Install on Linux/WSL: sudo apt install osmium-tool")
        sys.exit(1)

    print(f"  Output: {OSM_PBF_STUDY} ({OSM_PBF_STUDY.stat().st_size / 1e6:.1f} MB)")


def extract_buildings():
    """
    Extract building footprints from OSM via osmnx (Overpass API).
    Requires internet. Works on Windows without pyrosm.
    """
    bbox = VIZ_BBOX
    print(f"Extracting buildings for viz area (via osmnx/Overpass)...")
    print(f"  Bbox: W:{bbox['west']} S:{bbox['south']} E:{bbox['east']} N:{bbox['north']}")

    buildings = ox.features_from_bbox(
        bbox=(bbox["west"], bbox["south"], bbox["east"], bbox["north"]),
        tags={"building": True},
    )

    if buildings is None or len(buildings) == 0:
        print("  WARNING: No buildings found")
        return {"type": "buildings", "count": 0, "features": []}

    # Filter to Polygon geometries only
    buildings = buildings[buildings.geometry.type == "Polygon"].copy()
    print(f"  Found {len(buildings)} building polygons")

    def get_height(row):
        levels = row.get("building:levels", None)
        if levels is not None:
            try:
                h = float(levels) * 3.0
                if np.isfinite(h):
                    return h
            except (ValueError, TypeError):
                pass
        return 9.0  # Default 3 stories

    features = []
    for _, row in buildings.iterrows():
        coords = list(row.geometry.exterior.coords)
        coords_lnglat = [[round(c[0], 6), round(c[1], 6)] for c in coords]
        features.append({
            "coords": coords_lnglat,
            "height": round(get_height(row), 1),
        })

    output = {"type": "buildings", "count": len(features), "features": features}

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORT_DIR / "buildings.json"
    with open(out_path, "w") as f:
        json.dump(output, f)

    size_mb = out_path.stat().st_size / 1e6
    print(f"  Exported {len(features)} buildings to {out_path.name} ({size_mb:.1f} MB)")
    return output


def extract_roads():
    """
    Extract road network from OSM via osmnx (Overpass API).
    Requires internet. Works on Windows without pyrosm.
    """
    bbox = VIZ_BBOX
    print(f"Extracting road network for viz area (via osmnx/Overpass)...")
    print(f"  Bbox: W:{bbox['west']} S:{bbox['south']} E:{bbox['east']} N:{bbox['north']}")

    G = ox.graph_from_bbox(
        bbox=(bbox["west"], bbox["south"], bbox["east"], bbox["north"]),
        network_type="drive",
    )
    _, edges = ox.graph_to_gdfs(G)
    print(f"  Found {len(edges)} road segments")

    lat_center = (bbox["south"] + bbox["north"]) / 2
    segments = []
    for idx, row in edges.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "MultiLineString":
            coords_list = list(geom.geoms[0].coords)
        elif geom.geom_type == "LineString":
            coords_list = list(geom.coords)
        else:
            continue

        coords_lnglat = [[round(c[0], 6), round(c[1], 6)] for c in coords_list]

        highway = row.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]
        if highway is None:
            highway = "unclassified"

        lanes_raw = row.get("lanes", None)
        if lanes_raw is not None:
            try:
                lanes = int(float(str(lanes_raw)))
            except (ValueError, TypeError):
                lanes = DEFAULT_LANES.get(highway, 1)
        else:
            lanes = DEFAULT_LANES.get(highway, 1)

        maxspeed = row.get("maxspeed", None)
        if maxspeed is not None:
            try:
                speed_val = float(str(maxspeed).replace(" mph", "").replace(" km/h", ""))
                speed_kmh = speed_val if "km/h" in str(maxspeed) else speed_val * 1.60934
                if np.isnan(speed_kmh):
                    speed_kmh = 50.0
            except (ValueError, TypeError):
                speed_kmh = 50.0
        else:
            speed_kmh = 50.0

        name = row.get("name", "") or ""
        cap_per_lane = CAPACITY_PER_LANE.get(highway, 1000)

        length_m = row.get("length", geom.length * 111320 * np.cos(np.radians(lat_center)))

        segments.append({
            "id": f"seg_{idx}",
            "coords": coords_lnglat,
            "highway": str(highway),
            "lanes": lanes,
            "name": str(name),
            "length_m": round(float(length_m), 1),
            "capacity_per_hour": cap_per_lane * lanes,
            "free_flow_speed_kmh": round(speed_kmh, 1),
        })

    output = {"type": "road_network", "count": len(segments), "segments": segments}

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORT_DIR / "roads.json"
    with open(out_path, "w") as f:
        json.dump(output, f)

    size_mb = out_path.stat().st_size / 1e6
    print(f"  Exported {len(segments)} road segments to {out_path.name} ({size_mb:.1f} MB)")
    return output


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Prepare data for suburban simulation")
    parser.add_argument("--step", choices=["clip", "extract", "all"], default="all",
                        help="Which step to run (clip needs osmium/WSL, extract works on Mac)")
    args = parser.parse_args()

    if args.step in ("clip", "all"):
        clip_osm_to_study_area()

    if args.step in ("extract", "all"):
        extract_buildings()
        extract_roads()

    print("\nData preparation complete!")


if __name__ == "__main__":
    main()

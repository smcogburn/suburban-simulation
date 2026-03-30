"""
Export GTFS route shapes to JSON for the transit x-ray overlay in the visualization.

Reads shapes.txt from each baseline GTFS feed, filters to shapes that pass
through the study area, and writes data/export/transit_routes.json.

Run independently — does not require the full pipeline:
    python -m analysis.export_transit_routes
"""

import json
import zipfile
from pathlib import Path

import pandas as pd
from shapely.geometry import LineString

from analysis.config import GTFS_BASELINE_DIR, GTFS_FEEDS, EXPORT_DIR, VIZ_BBOX

# Route type → human-readable label
ROUTE_TYPE_LABELS = {
    0: "Tram",
    1: "Metro",
    2: "Rail",
    3: "Bus",
    4: "Ferry",
    5: "Cable Car",
    11: "Trolleybus",
    12: "Monorail",
}

# Default colors per route type (if GTFS doesn't specify)
ROUTE_TYPE_COLORS = {
    0: "#ffcc00",
    1: "#ff6600",
    2: "#ff6600",
    3: "#4488ff",
    4: "#44aaff",
    11: "#88ccff",
    12: "#ff8800",
}

# Simplification: keep every Nth shape point (reduces JSON size)
SIMPLIFY_EVERY_N = 3

# Only keep shapes with at least this fraction of points inside VIZ_BBOX
MIN_FRACTION_IN_BBOX = 0.05


def read_gtfs_table(zf: zipfile.ZipFile, filename: str) -> pd.DataFrame | None:
    """Read a CSV table from a GTFS zip, return None if not present."""
    try:
        with zf.open(filename) as f:
            return pd.read_csv(f, dtype=str, low_memory=False)
    except KeyError:
        return None


def in_bbox(lat: float, lng: float) -> bool:
    b = VIZ_BBOX
    return b["west"] <= lng <= b["east"] and b["south"] <= lat <= b["north"]


def _reconstruct_shapes_from_stops(zf: zipfile.ZipFile, routes_df) -> pd.DataFrame | None:
    """
    When shapes.txt is empty, build route geometry from stop_times + stops.
    Each route gets one synthetic shape: the ordered sequence of stops for its
    most representative trip. Lines are stop-to-stop straight segments, which
    is good enough for a visualization overlay.
    """
    stops_df = read_gtfs_table(zf, "stops.txt")
    trips_df = read_gtfs_table(zf, "trips.txt")
    stop_times_df = read_gtfs_table(zf, "stop_times.txt")

    if stops_df is None or trips_df is None or stop_times_df is None:
        return None

    stops_df["stop_lat"] = pd.to_numeric(stops_df["stop_lat"], errors="coerce")
    stops_df["stop_lon"] = pd.to_numeric(stops_df["stop_lon"], errors="coerce")
    stop_coords = stops_df.set_index("stop_id")[["stop_lat", "stop_lon"]]

    stop_times_df["stop_sequence"] = pd.to_numeric(stop_times_df["stop_sequence"], errors="coerce")

    rows = []
    for route_id, route_trips in trips_df.groupby("route_id"):
        # Pick the first trip for this route
        trip_id = route_trips["trip_id"].iloc[0]
        shape_id = f"reconstructed_{route_id}"

        trip_stops = stop_times_df[stop_times_df["trip_id"] == trip_id].sort_values("stop_sequence")
        for seq, (_, st_row) in enumerate(trip_stops.iterrows()):
            sid = st_row["stop_id"]
            if sid not in stop_coords.index:
                continue
            lat = stop_coords.loc[sid, "stop_lat"]
            lon = stop_coords.loc[sid, "stop_lon"]
            if pd.isna(lat) or pd.isna(lon):
                continue
            rows.append({
                "shape_id": shape_id,
                "shape_pt_lat": lat,
                "shape_pt_lon": lon,
                "shape_pt_sequence": seq,
            })

        # Back-assign shape_id to trips so route lookup works
        trips_df.loc[trips_df["route_id"] == route_id, "shape_id"] = shape_id

    if not rows:
        return None, trips_df

    return pd.DataFrame(rows), trips_df


def export_transit_routes():
    all_routes = []

    for feed_name in GTFS_FEEDS:
        feed_path = GTFS_BASELINE_DIR / feed_name
        if not feed_path.exists():
            print(f"  Skipping {feed_name} (not found)")
            continue

        print(f"  Processing {feed_name}...")

        with zipfile.ZipFile(feed_path) as zf:
            shapes_df = read_gtfs_table(zf, "shapes.txt")
            routes_df = read_gtfs_table(zf, "routes.txt")
            trips_df  = read_gtfs_table(zf, "trips.txt")

            if shapes_df is None or trips_df is None:
                print(f"    No shapes.txt or trips.txt — skipping")
                continue

            # Build shape_id → route_id mapping via trips
            shape_to_route = trips_df.drop_duplicates("shape_id").set_index("shape_id")["route_id"]

            # Build route color/name lookup
            route_info = {}
            if routes_df is not None:
                for _, row in routes_df.iterrows():
                    rid = row.get("route_id", "")
                    rtype = int(row.get("route_type", 3) or 3)
                    color_hex = str(row.get("route_color", "") or "").strip()
                    if color_hex and len(color_hex) == 6:
                        color = f"#{color_hex}"
                    else:
                        color = ROUTE_TYPE_COLORS.get(rtype, "#4488ff")
                    name = (row.get("route_short_name") or row.get("route_long_name") or rid).strip()
                    route_info[rid] = {
                        "name": name,
                        "color": color,
                        "type": ROUTE_TYPE_LABELS.get(rtype, "Bus"),
                    }

            # Convert shape points to float
            shapes_df["shape_pt_lat"] = pd.to_numeric(shapes_df["shape_pt_lat"], errors="coerce")
            shapes_df["shape_pt_lon"] = pd.to_numeric(shapes_df["shape_pt_lon"], errors="coerce")
            shapes_df["shape_pt_sequence"] = pd.to_numeric(shapes_df["shape_pt_sequence"], errors="coerce")
            shapes_df = shapes_df.dropna(subset=["shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])

            # If shapes.txt is empty, reconstruct geometry from stop sequences
            if shapes_df is None or len(shapes_df) == 0:
                print(f"    shapes.txt is empty — reconstructing from stop sequences")
                shapes_df, trips_df = _reconstruct_shapes_from_stops(zf, routes_df)
                if shapes_df is None:
                    print(f"    Could not reconstruct shapes — skipping")
                    continue
                # Rebuild shape→route mapping with reconstructed shape_ids
                shape_to_route = trips_df.drop_duplicates("shape_id").dropna(subset=["shape_id"]).set_index("shape_id")["route_id"]

            # Group by shape_id
            seen_shapes = set()
            for shape_id, grp in shapes_df.groupby("shape_id"):
                grp = grp.sort_values("shape_pt_sequence")
                coords = list(zip(grp["shape_pt_lon"], grp["shape_pt_lat"]))

                if not coords:
                    continue

                # Filter: must have some points inside VIZ_BBOX
                in_box = sum(1 for lng, lat in coords if in_bbox(lat, lng))
                if in_box / len(coords) < MIN_FRACTION_IN_BBOX:
                    continue

                # Clip: only keep the portion of the shape near the study area
                # (keep points within bbox + 10km buffer to avoid hard cutoffs)
                BUFFER = 0.09  # ~10km in degrees at this latitude
                b = VIZ_BBOX
                clipped = [
                    (lng, lat) for lng, lat in coords
                    if (b["west"] - BUFFER) <= lng <= (b["east"] + BUFFER)
                    and (b["south"] - BUFFER) <= lat <= (b["north"] + BUFFER)
                ]
                if len(clipped) < 2:
                    continue

                # Simplify by taking every Nth point (keep first and last)
                simplified = clipped[::SIMPLIFY_EVERY_N]
                if simplified[-1] != clipped[-1]:
                    simplified.append(clipped[-1])

                # Round to 5 decimal places (~1m precision)
                simplified = [[round(lng, 5), round(lat, 5)] for lng, lat in simplified]

                # Get route info
                route_id = shape_to_route.get(shape_id, "unknown")
                info = route_info.get(route_id, {"name": route_id, "color": "#4488ff", "type": "Bus"})

                # De-duplicate: skip if same route_id already has a very similar shape
                route_key = f"{route_id}_{len(simplified)}"
                if route_key in seen_shapes:
                    continue
                seen_shapes.add(route_key)

                all_routes.append({
                    "route_id": route_id,
                    "shape_id": shape_id,
                    "name": info["name"],
                    "type": info["type"],
                    "color": info["color"],
                    "path": simplified,
                })

        print(f"    → {len([r for r in all_routes if r])} routes so far")

    # Sort by type then name for predictable ordering
    all_routes.sort(key=lambda r: (r["type"], r["name"]))

    out = {
        "count": len(all_routes),
        "routes": all_routes,
    }

    out_path = EXPORT_DIR / "transit_routes.json"
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"\nExported {len(all_routes)} route shapes → {out_path.name} ({size_kb:.0f} KB)")
    for r in all_routes[:20]:
        print(f"  [{r['type']}] {r['name']} — {len(r['path'])} points")
    if len(all_routes) > 20:
        print(f"  ... and {len(all_routes) - 20} more")


if __name__ == "__main__":
    export_transit_routes()


# Also importable from run_pipeline if desired
if __name__ == "__main__":
    export_transit_routes()

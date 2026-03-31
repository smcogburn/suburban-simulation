"""
GTFS clipper: bbox + peak-window filter.

Two problems were causing 188-minute runs:
  1. PG County (81k stop_times): full-day service, bbox covers most of it.
  2. MTA local bus (1.375M stop_times): statewide feed, bbox filter very effective.

This script applies BOTH filters to every feed:
  - Spatial: keep trips with at least one stop inside ANALYSIS_BBOX (+ buffer).
  - Temporal: keep only those trips whose first departure is within the
    morning rush window (5:00–11:00 AM).

Together these reduce MTA local bus from 1.375M -> ~30-50k stop_times and
PG County from 81k -> ~20k. r5py network build time drops from ~3 hours -> ~20 min.

Run once before the pipeline (or whenever GTFS feeds change):
    python -m analysis.clip_gtfs

Safe to re-run: already-small feeds (< SKIP_THRESHOLD) are skipped.
Overwrites the zip in place — originals are gitignored and re-downloadable.
"""

import io
import os
import zipfile
from pathlib import Path

import pandas as pd

from analysis.config import GTFS_BASELINE_DIR, GTFS_FEEDS, ANALYSIS_BBOX

# ── Spatial filter ───────────────────────────────────────────────────────────
# Keep trips with at least one stop inside this box (+ buffer).
# Buffer of 0.1° (~10 km) includes routes that enter the area from outside.
BBOX_BUFFER = 0.10
WEST  = ANALYSIS_BBOX["west"]  - BBOX_BUFFER
EAST  = ANALYSIS_BBOX["east"]  + BBOX_BUFFER
SOUTH = ANALYSIS_BBOX["south"] - BBOX_BUFFER
NORTH = ANALYSIS_BBOX["north"] + BBOX_BUFFER

# ── Temporal filter ──────────────────────────────────────────────────────────
# Keep trips whose first stop departs between 5:00 AM and 11:00 AM.
# Covers our 7–9:30 AM rush with generous buffer. Drops midday / PM / late-night.
WINDOW_START_SEC = 5 * 3600   # 05:00 = 18 000
WINDOW_END_SEC   = 11 * 3600  # 11:00 = 39 600

# Feeds already below this size are skipped (fast re-run safety).
SKIP_THRESHOLD = 5_000


def _to_seconds(t: str) -> int | None:
    """HH:MM:SS -> seconds since midnight. Returns None on parse error."""
    try:
        h, m, s = str(t).strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except (ValueError, AttributeError):
        return None


def clip_feed(feed_path: Path) -> None:
    """Apply bbox + time-window filter to one GTFS zip, overwriting in place."""
    print(f"\n  {feed_path.name}")

    # ── Load tables ──────────────────────────────────────────────────────────
    with zipfile.ZipFile(feed_path, "r") as z:
        names = set(z.namelist())

        def read(filename):
            return (pd.read_csv(io.BytesIO(z.read(filename)), dtype=str)
                    if filename in names else None)

        stop_times  = read("stop_times.txt")
        trips       = read("trips.txt")
        stops       = read("stops.txt")
        routes      = read("routes.txt")
        calendar    = read("calendar.txt")
        cal_dates   = read("calendar_dates.txt")
        shapes      = read("shapes.txt")
        agency      = read("agency.txt")
        feed_info   = read("feed_info.txt")
        passthrough = {n: z.read(n) for n in names
                       if n not in {"stop_times.txt", "trips.txt", "stops.txt",
                                    "routes.txt", "calendar.txt", "calendar_dates.txt",
                                    "shapes.txt", "agency.txt", "feed_info.txt"}}

    if stop_times is None or trips is None:
        print(f"    Missing stop_times.txt or trips.txt — skipping.")
        return

    n_st_orig = len(stop_times)
    n_tr_orig = len(trips)

    if n_st_orig < SKIP_THRESHOLD:
        print(f"    Already small ({n_st_orig:,} stop_times) — skipping.")
        return

    # ── Step 1: spatial filter — stops inside bbox ───────────────────────────
    if stops is not None:
        stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
        stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
        in_bbox_mask = (
            stops["stop_lat"].between(SOUTH, NORTH) &
            stops["stop_lon"].between(WEST,  EAST)
        )
        stops_in_bbox = set(stops.loc[in_bbox_mask, "stop_id"])
    else:
        # No stops.txt — can't spatial-filter; fall through to time filter only
        stops_in_bbox = None

    # ── Step 2: trips with at least one stop in bbox ─────────────────────────
    if stops_in_bbox is not None:
        trips_in_bbox = set(
            stop_times.loc[stop_times["stop_id"].isin(stops_in_bbox), "trip_id"]
        )
        # Narrow stop_times to bbox-touching trips before time filter
        st_candidate = stop_times[stop_times["trip_id"].isin(trips_in_bbox)]
    else:
        trips_in_bbox = set(stop_times["trip_id"])
        st_candidate  = stop_times

    n_after_bbox = len(trips_in_bbox)

    # ── Step 3: temporal filter — first departure in window ──────────────────
    st_candidate = st_candidate.copy()
    st_candidate["_seq"] = pd.to_numeric(st_candidate.get("stop_sequence"), errors="coerce")
    first_dep = (
        st_candidate.sort_values("_seq")
        .groupby("trip_id", sort=False)["departure_time"]
        .first()
        .reset_index()
    )
    first_dep["_sec"] = first_dep["departure_time"].apply(_to_seconds)

    keep_trip_ids = set(
        first_dep.loc[
            first_dep["_sec"].between(WINDOW_START_SEC, WINDOW_END_SEC),
            "trip_id",
        ]
    )

    if not keep_trip_ids:
        print(f"    WARNING: no trips survive both filters — feed unchanged.")
        return

    # ── Step 4: cascade filter remaining tables ───────────────────────────────
    stop_times_out = stop_times[stop_times["trip_id"].isin(keep_trip_ids)].drop(
        columns=["_seq"], errors="ignore"
    )
    trips_out = trips[trips["trip_id"].isin(keep_trip_ids)]

    used_stop_ids    = set(stop_times_out["stop_id"])
    used_route_ids   = set(trips_out["route_id"])   if "route_id"   in trips_out else set()
    used_service_ids = set(trips_out["service_id"]) if "service_id" in trips_out else set()
    used_shape_ids   = set(trips_out["shape_id"].dropna()) if "shape_id" in trips_out else set()

    stops_out     = (stops[stops["stop_id"].isin(used_stop_ids)]
                     if stops    is not None else None)
    routes_out    = (routes[routes["route_id"].isin(used_route_ids)]
                     if routes   is not None else None)
    calendar_out  = (calendar[calendar["service_id"].isin(used_service_ids)]
                     if calendar is not None else None)
    cal_dates_out = (cal_dates[cal_dates["service_id"].isin(used_service_ids)]
                     if cal_dates is not None else None)
    shapes_out    = (shapes[shapes["shape_id"].isin(used_shape_ids)]
                     if shapes is not None and used_shape_ids else shapes)

    # ── Print summary ─────────────────────────────────────────────────────────
    pct = 100 * len(stop_times_out) / n_st_orig
    print(f"    stop_times:  {n_st_orig:>9,}  ->  {len(stop_times_out):>7,}  ({pct:.0f}% kept)")
    print(f"    trips:       {n_tr_orig:>9,}  ->  {len(trips_out):>7,}"
          f"  ({n_after_bbox} survived bbox, {len(keep_trip_ids)} survived time filter)")
    if stops is not None and stops_out is not None:
        print(f"    stops:       {len(stops):>9,}  ->  {len(stops_out):>7,}")

    # ── Write back atomically ────────────────────────────────────────────────
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        def write_df(df, name):
            if df is not None:
                zout.writestr(name, df.to_csv(index=False))

        write_df(stop_times_out,  "stop_times.txt")
        write_df(trips_out,       "trips.txt")
        write_df(stops_out,       "stops.txt")
        write_df(routes_out,      "routes.txt")
        write_df(calendar_out,    "calendar.txt")
        write_df(cal_dates_out,   "calendar_dates.txt")
        write_df(shapes_out,      "shapes.txt")
        write_df(agency,          "agency.txt")
        write_df(feed_info,       "feed_info.txt")
        for name, data in passthrough.items():
            zout.writestr(name, data)

    tmp = str(feed_path) + ".tmp"
    with open(tmp, "wb") as f:
        f.write(buf.getvalue())
    os.replace(tmp, feed_path)

    size_kb = feed_path.stat().st_size / 1024
    print(f"    -> written ({size_kb:.0f} KB)")


def clip_all_feeds(gtfs_dir: Path = GTFS_BASELINE_DIR) -> None:
    print("=" * 60)
    print("GTFS CLIPPER  (bbox + peak-window)")
    print(f"  Bbox:   W={WEST:.2f}  E={EAST:.2f}  S={SOUTH:.2f}  N={NORTH:.2f}  (+/-{BBOX_BUFFER}deg buffer)")
    print(f"  Window: {WINDOW_START_SEC//3600}:00 - {WINDOW_END_SEC//3600}:00 (first trip departure)")
    print(f"  Dir:    {gtfs_dir}")
    print("=" * 60)

    found = 0
    for feed_name in GTFS_FEEDS:
        feed_path = gtfs_dir / feed_name
        if not feed_path.exists():
            print(f"\n  {feed_name}: not found, skipping")
            continue
        clip_feed(feed_path)
        found += 1

    print(f"\nDone. Processed {found} feeds in {gtfs_dir}")
    print("Re-run scenario_builder.py to rebuild Policy A from the clipped feeds.")


if __name__ == "__main__":
    clip_all_feeds()

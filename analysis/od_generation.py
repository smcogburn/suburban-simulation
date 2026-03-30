"""
Origin-Destination pair generation.

Generates synthetic trip origins (residential locations) and destinations
(employment/commercial centers) from OSM data, then creates the OD matrix
with assigned departure times.
"""

import random
from typing import Optional

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import Point

from analysis.config import (
    ANALYSIS_BBOX,
    VIZ_BBOX,
    NUM_ORIGINS,
    NUM_DESTINATIONS,
    NUM_REGIONAL_DESTINATIONS,
    NUM_LOCAL_DESTINATIONS,
    LOCAL_TRIP_RADIUS_KM,
    DEPARTURE_DATE,
    DEPARTURE_SLOTS,
    VIZ_TRIP_SUBSET,
)


def get_residential_origins(num_origins: int = NUM_ORIGINS) -> gpd.GeoDataFrame:
    """
    Sample residential building centroids as trip origins.
    Uses ANALYSIS_BBOX (full Bowie/Crofton/Annapolis corridor) for realistic suburban commutes.
    Falls back to random points within the study area if OSM data is sparse.
    """
    bbox = ANALYSIS_BBOX
    print(f"Generating {num_origins} origin points from residential buildings...")

    try:
        # Try to get residential buildings from OSM
        buildings = ox.features_from_bbox(
            bbox=(bbox["west"], bbox["south"], bbox["east"], bbox["north"]),
            tags={"building": ["residential", "apartments", "house", "detached", "yes"]},
        )
        buildings = buildings[buildings.geometry.type.isin(["Polygon", "MultiPolygon"])]
        print(f"  Found {len(buildings)} residential buildings in OSM")

        if len(buildings) < num_origins:
            print(f"  Warning: fewer buildings than requested origins, using all {len(buildings)}")
            num_origins = len(buildings)

        # Calculate footprint area as sampling weight (larger buildings = more residents)
        buildings_proj = buildings.to_crs(epsg=3857)
        buildings["area"] = buildings_proj.geometry.area
        weights = buildings["area"] / buildings["area"].sum()

        # Weighted random sample — compute centroids in projected CRS to avoid warning
        sampled = buildings.sample(n=num_origins, weights=weights, random_state=42)
        centroids = sampled.to_crs(epsg=3857).geometry.centroid.to_crs("EPSG:4326")

    except Exception as e:
        print(f"  Warning: Could not get buildings from OSM: {e}")
        print(f"  Falling back to random points within study area")
        rng = np.random.default_rng(42)
        lngs = rng.uniform(bbox["west"], bbox["east"], num_origins)
        lats = rng.uniform(bbox["south"], bbox["north"], num_origins)
        centroids = gpd.GeoSeries([Point(lng, lat) for lng, lat in zip(lngs, lats)], crs="EPSG:4326")

    origins = gpd.GeoDataFrame(
        {"id": [f"origin_{i}" for i in range(len(centroids))]},
        geometry=centroids.values,
        crs="EPSG:4326",
    )
    origins = origins.reset_index(drop=True)
    print(f"  Generated {len(origins)} origins")
    return origins


def get_destinations() -> gpd.GeoDataFrame:
    """
    Sample destinations from OSM in two pools, tagged by type:

    - "regional" (NUM_REGIONAL_DESTINATIONS): major employment/commercial across
      the full corridor. Every origin is paired with every regional destination
      (commute trips — expected to be long, car-dominant, realistic).

    - "local" (NUM_LOCAL_DESTINATIONS): grocery stores, schools, pharmacies, cafes
      sampled corridor-wide. In create_od_matrix(), each origin is only paired with
      local destinations within LOCAL_TRIP_RADIUS_KM — ensuring local trips are
      actually short and bike/walk-competitive.

    Returns GeoDataFrame with columns: id, type, geometry.
    """
    bbox = ANALYSIS_BBOX
    print(f"Generating destinations ({NUM_REGIONAL_DESTINATIONS} regional + up to {NUM_LOCAL_DESTINATIONS} local POIs)...")

    regional_geoms = []
    local_geoms = []

    # --- Pool 1: Regional destinations (employment/commercial) ---
    try:
        regional = ox.features_from_bbox(
            bbox=(bbox["west"], bbox["south"], bbox["east"], bbox["north"]),
            tags={
                "building": ["commercial", "office", "retail", "industrial"],
                "amenity": ["hospital", "university", "marketplace"],
            },
        )
        regional_centroids = regional.to_crs(epsg=3857).geometry.centroid.to_crs("EPSG:4326")
        if regional_centroids.crs is None:
            regional_centroids = regional_centroids.set_crs("EPSG:4326")

        n_regional = min(NUM_REGIONAL_DESTINATIONS, len(regional_centroids))
        idx = np.random.default_rng(42).choice(len(regional_centroids), n_regional, replace=False)
        regional_centroids = regional_centroids.iloc[idx]
        regional_geoms = list(regional_centroids.values)
        print(f"  Regional destinations: {len(regional_geoms)} sampled from {len(regional_centroids)} candidates")

    except Exception as e:
        print(f"  Warning: Could not get regional destinations: {e}")

    # --- Pool 2: Local amenities (grocery, school, pharmacy, cafe) ---
    # Sample corridor-wide — proximity filtering happens in create_od_matrix()
    try:
        local = ox.features_from_bbox(
            bbox=(bbox["west"], bbox["south"], bbox["east"], bbox["north"]),
            tags={
                "shop": ["supermarket", "convenience", "department_store", "grocery"],
                "amenity": ["school", "pharmacy", "restaurant", "cafe", "library", "community_centre"],
            },
        )
        local_centroids = local.to_crs(epsg=3857).geometry.centroid.to_crs("EPSG:4326")
        if local_centroids.crs is None:
            local_centroids = local_centroids.set_crs("EPSG:4326")

        n_local = min(NUM_LOCAL_DESTINATIONS, len(local_centroids))
        idx = np.random.default_rng(43).choice(len(local_centroids), n_local, replace=False)
        local_centroids = local_centroids.iloc[idx]
        local_geoms = list(local_centroids.values)
        print(f"  Local POIs: {len(local_geoms)} sampled corridor-wide (proximity-filtered per origin at {LOCAL_TRIP_RADIUS_KM} km)")

    except Exception as e:
        print(f"  Warning: Could not get local destinations: {e}")

    # --- Combine with type tags ---
    if not regional_geoms and not local_geoms:
        print("  Falling back to manually defined destinations")
        fallback = _fallback_destinations()
        destinations = gpd.GeoDataFrame(
            {"id": [f"dest_{i}" for i in range(len(fallback))], "type": "regional"},
            geometry=fallback.values,
            crs="EPSG:4326",
        )
        return destinations

    rows = []
    for i, geom in enumerate(regional_geoms):
        rows.append({"id": f"regional_{i}", "type": "regional", "geometry": geom})
    for i, geom in enumerate(local_geoms):
        rows.append({"id": f"local_{i}", "type": "local", "geometry": geom})

    destinations = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    destinations = destinations.reset_index(drop=True)
    print(f"  Total destination pool: {len(destinations)} ({len(regional_geoms)} regional + {len(local_geoms)} local)")
    return destinations


def _fallback_destinations() -> gpd.GeoSeries:
    """
    Manually defined major destinations in the Bowie/Crofton/Annapolis area.
    Used as fallback if OSM data extraction fails.
    """
    locations = {
        "Annapolis Mall": (-76.5557, 38.9820),
        "Annapolis Downtown": (-76.4922, 38.9784),
        "US Naval Academy": (-76.4852, 38.9832),
        "Annapolis Town Center": (-76.5480, 38.9958),
        "Bowie Town Center": (-76.7313, 38.9470),
        "Bowie State University": (-76.7302, 38.9446),
        "Crofton Commons": (-76.6832, 38.9971),
        "Crofton Village Center": (-76.6861, 39.0069),
        "Waugh Chapel Towne Centre": (-76.6703, 39.0094),
        "Fort Meade": (-76.7323, 39.1031),
        "Odenton MARC Station": (-76.6999, 39.0773),
        "Severna Park": (-76.5488, 39.0677),
        "Glen Burnie": (-76.6280, 39.1631),
        "Gambrills": (-76.6652, 39.0466),
        "Parole": (-76.5375, 38.9976),
    }

    return gpd.GeoSeries(
        [Point(lng, lat) for lng, lat in locations.values()],
        crs="EPSG:4326",
    )


def create_od_matrix(
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Create OD pairs with proximity-aware logic:

    - Regional destinations: every origin → every regional destination (commute trips).
      These are long-distance by design — realistic suburban commutes, car-dominant.

    - Local destinations: each origin → only local destinations within
      LOCAL_TRIP_RADIUS_KM. This ensures local trips (grocery, school, pharmacy)
      are actually walkable/bikeable distances.

    Returns DataFrame with columns:
        from_id, to_id, trip_type, from_geometry, to_geometry,
        departure_time, departure_seconds
    """
    print("Creating proximity-aware OD matrix...")

    # Project to meters for distance calculation (UTM zone 18N covers Maryland)
    UTM = "EPSG:32618"
    origins_proj = origins.to_crs(UTM)
    destinations_proj = destinations.to_crs(UTM)
    radius_m = LOCAL_TRIP_RADIUS_KM * 1000

    regional_mask = destinations["type"] == "regional"
    local_mask = destinations["type"] == "local"
    regional_dests = destinations[regional_mask].reset_index(drop=True)
    local_dests = destinations[local_mask].reset_index(drop=True)
    local_dests_proj = destinations_proj[local_mask].reset_index(drop=True)

    print(f"  Regional dests: {len(regional_dests)}, Local POI pool: {len(local_dests)}")

    rng = np.random.default_rng(seed)
    rows = []

    def _make_row(origin, dest, trip_type):
        slot = DEPARTURE_SLOTS[rng.integers(0, len(DEPARTURE_SLOTS))]
        departure_dt = pd.Timestamp.combine(DEPARTURE_DATE, slot)
        seconds_since_7am = (slot.hour - 7) * 3600 + slot.minute * 60
        return {
            "from_id": origin["id"],
            "to_id": dest["id"],
            "trip_type": trip_type,
            "from_geometry": origin.geometry,
            "to_geometry": dest.geometry,
            "departure_time": departure_dt,
            "departure_seconds": seconds_since_7am,
        }

    local_counts = []
    for i, (_, origin) in enumerate(origins.iterrows()):
        origin_proj = origins_proj.iloc[i]

        # Commute: every origin → every regional destination
        for _, dest in regional_dests.iterrows():
            rows.append(_make_row(origin, dest, "commute"))

        # Local: only destinations within radius
        n_local = 0
        for j, (_, local_dest) in enumerate(local_dests.iterrows()):
            dist = origin_proj.geometry.distance(local_dests_proj.iloc[j].geometry)
            if dist <= radius_m:
                rows.append(_make_row(origin, local_dest, "local"))
                n_local += 1
        local_counts.append(n_local)

    od_matrix = pd.DataFrame(rows)

    commute_count = (od_matrix["trip_type"] == "commute").sum()
    local_count = (od_matrix["trip_type"] == "local").sum()
    print(f"  Total OD pairs: {len(od_matrix)} ({commute_count} commute + {local_count} local)")
    print(f"  Local trips per origin — avg: {np.mean(local_counts):.1f}, "
          f"min: {min(local_counts)}, max: {max(local_counts)}")

    slot_counts = od_matrix["departure_time"].dt.time.value_counts().sort_index()
    print(f"  Departure time distribution:")
    for slot_time, count in slot_counts.items():
        print(f"    {slot_time.strftime('%H:%M')}: {count} trips")

    return od_matrix


def select_viz_subset(
    od_matrix: pd.DataFrame,
    n: int = VIZ_TRIP_SUBSET,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Select a representative subset of OD pairs for DetailedItineraries.
    These are the trips that will have path geometry for the 3D visualization.
    Stratified by departure time to ensure coverage across the rush period.
    """
    print(f"Selecting {n} OD pairs for visualization subset (stratified by departure time)...")

    if len(od_matrix) <= n:
        print(f"  OD matrix ({len(od_matrix)}) is smaller than subset size, using all")
        return od_matrix

    # Stratified sample: proportional to departure time distribution
    sampled = od_matrix.groupby(
        od_matrix["departure_time"].dt.time, group_keys=False
    ).apply(
        lambda group: group.sample(
            n=min(len(group), n // len(DEPARTURE_SLOTS)),
            random_state=seed,
        )
    )

    # If we need more to reach n, sample from remainder
    if len(sampled) < n:
        remaining = od_matrix.drop(sampled.index)
        extra = remaining.sample(n=n - len(sampled), random_state=seed)
        sampled = pd.concat([sampled, extra])

    print(f"  Selected {len(sampled)} OD pairs for visualization")
    return sampled.reset_index(drop=True)


def main():
    """Generate and save OD data."""
    origins = get_residential_origins()
    destinations = get_destinations()
    od_matrix = create_od_matrix(origins, destinations)
    viz_subset = select_viz_subset(od_matrix)

    print(f"\nSummary:")
    print(f"  Origins: {len(origins)}")
    print(f"  Destinations: {len(destinations)}")
    print(f"  Total OD pairs: {len(od_matrix)}")
    print(f"  Viz subset: {len(viz_subset)}")

    return origins, destinations, od_matrix, viz_subset


if __name__ == "__main__":
    main()

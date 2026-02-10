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
    VIZ_BBOX,
    NUM_ORIGINS,
    NUM_DESTINATIONS,
    DEPARTURE_DATE,
    DEPARTURE_SLOTS,
    VIZ_TRIP_SUBSET,
)


def get_residential_origins(num_origins: int = NUM_ORIGINS) -> gpd.GeoDataFrame:
    """
    Sample residential building centroids as trip origins.
    Falls back to random points within the study area if OSM data is sparse.
    """
    bbox = VIZ_BBOX
    print(f"Generating {num_origins} origin points from residential buildings...")

    try:
        # Try to get residential buildings from OSM
        buildings = ox.features_from_bbox(
            bbox=(bbox["north"], bbox["south"], bbox["east"], bbox["west"]),
            tags={"building": ["residential", "apartments", "house", "detached", "yes"]},
        )
        buildings = buildings[buildings.geometry.type.isin(["Polygon", "MultiPolygon"])]
        print(f"  Found {len(buildings)} residential buildings in OSM")

        if len(buildings) < num_origins:
            print(f"  Warning: fewer buildings than requested origins, using all {len(buildings)}")
            num_origins = len(buildings)

        # Calculate footprint area as sampling weight (larger buildings = more residents)
        buildings_proj = buildings.to_crs(epsg=3857)  # Project for area calculation
        buildings["area"] = buildings_proj.geometry.area
        weights = buildings["area"] / buildings["area"].sum()

        # Weighted random sample
        sampled = buildings.sample(n=num_origins, weights=weights, random_state=42)
        centroids = sampled.geometry.centroid

    except Exception as e:
        print(f"  Warning: Could not get buildings from OSM: {e}")
        print(f"  Falling back to random points within study area")
        # Generate random points within bounding box
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


def get_destinations(num_destinations: int = NUM_DESTINATIONS) -> gpd.GeoDataFrame:
    """
    Sample commercial/employment destinations from OSM.
    Falls back to manually defined Columbia-area destinations if OSM data is sparse.
    """
    bbox = VIZ_BBOX
    print(f"Generating {num_destinations} destination points...")

    try:
        # Get commercial/office buildings and amenities
        commercial = ox.features_from_bbox(
            bbox=(bbox["north"], bbox["south"], bbox["east"], bbox["west"]),
            tags={
                "building": ["commercial", "office", "retail", "industrial"],
                "amenity": ["school", "hospital", "university", "marketplace"],
                "shop": True,
            },
        )

        # Get centroids for all features
        centroids = commercial.geometry.centroid
        # Make sure they're points in WGS84
        if centroids.crs is None:
            centroids = centroids.set_crs("EPSG:4326")

        print(f"  Found {len(centroids)} commercial/amenity features in OSM")

        if len(centroids) >= num_destinations:
            # Random sample
            indices = np.random.default_rng(42).choice(
                len(centroids), num_destinations, replace=False
            )
            centroids = centroids.iloc[indices]
        else:
            print(f"  Using all {len(centroids)} available features")

    except Exception as e:
        print(f"  Warning: Could not get destinations from OSM: {e}")
        print(f"  Using manually defined Columbia-area destinations")
        centroids = _fallback_destinations()

    destinations = gpd.GeoDataFrame(
        {"id": [f"dest_{i}" for i in range(len(centroids))]},
        geometry=centroids.values,
        crs="EPSG:4326",
    )
    destinations = destinations.reset_index(drop=True)
    print(f"  Generated {len(destinations)} destinations")
    return destinations


def _fallback_destinations() -> gpd.GeoSeries:
    """
    Manually defined major destinations in the Columbia-Ellicott City area.
    Used as fallback if OSM data extraction fails.
    """
    locations = {
        "Columbia Town Center": (-76.8391, 39.2037),
        "Columbia Mall": (-76.8597, 39.2098),
        "Ellicott City Downtown": (-76.7987, 39.2674),
        "Gateway Business Park": (-76.8313, 39.2097),
        "Dobbin Road Business": (-76.8459, 39.2003),
        "Columbia Gateway": (-76.8262, 39.2046),
        "Snowden Square": (-76.8572, 39.1859),
        "Long Reach Village": (-76.8195, 39.2145),
        "Howard County Gen Hospital": (-76.8374, 39.2182),
        "Wilde Lake Village": (-76.8654, 39.2124),
        "Harper Choice Village": (-76.8711, 39.2066),
        "Oakland Mills Village": (-76.8390, 39.2098),
        "Owen Brown Village": (-76.8282, 39.1977),
        "Hickory Ridge Village": (-76.8596, 39.1960),
        "Kings Contrivance Village": (-76.8395, 39.1870),
    ]
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
    Create all origin-destination pairs with assigned departure times.
    Each OD pair gets a random departure slot from the morning rush period.

    Returns DataFrame with columns:
        from_id, to_id, from_geometry, to_geometry, departure_time, departure_seconds
    """
    print("Creating OD matrix...")

    rng = np.random.default_rng(seed)
    rows = []

    for _, origin in origins.iterrows():
        for _, dest in destinations.iterrows():
            # Assign a random departure slot
            slot = DEPARTURE_SLOTS[rng.integers(0, len(DEPARTURE_SLOTS))]
            departure_dt = pd.Timestamp.combine(DEPARTURE_DATE, slot)

            # Seconds since 7:00 AM (for the visualization time system)
            seconds_since_7am = (slot.hour - 7) * 3600 + slot.minute * 60

            rows.append({
                "from_id": origin["id"],
                "to_id": dest["id"],
                "from_geometry": origin.geometry,
                "to_geometry": dest.geometry,
                "departure_time": departure_dt,
                "departure_seconds": seconds_since_7am,
            })

    od_matrix = pd.DataFrame(rows)
    print(f"  Created {len(od_matrix)} OD pairs")
    print(f"  Departure time distribution:")
    for slot in DEPARTURE_SLOTS:
        count = sum(1 for _, r in od_matrix.iterrows()
                    if r["departure_time"].time() == slot)
        print(f"    {slot.strftime('%H:%M')}: {count} trips")

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

import geopandas
import r5py
import r5py.sampledata.helsinki
import shapely
import datetime
import pandas as pd

population_grid = geopandas.read_file(r5py.sampledata.helsinki.population_grid)

railway_station = geopandas.GeoDataFrame(
    {
        "id": ["railway_station"],
        "geometry": [shapely.Point(24.94152, 60.17066)]
    },
    crs="EPSG:4326",
)

overview_map = population_grid.explore("population", cmap="Reds")
overview_map = railway_station.explore(m=overview_map, marker_type="marker")

transport_network = r5py.TransportNetwork(
    r5py.sampledata.helsinki.osm_pbf,
    [r5py.sampledata.helsinki.gtfs],
    r5py.sampledata.helsinki.elevation_model,
)

origins = population_grid.copy()
# Convert to a projected CRS (EPSG:3067 is Finnish national grid)
origins = origins.to_crs("EPSG:3067")
origins.geometry = origins.geometry.centroid
# Convert back to WGS84 if needed for compatibility with other data
origins = origins.to_crs("EPSG:4326")

destinations = railway_station.copy()


travel_times = r5py.TravelTimeMatrix(
    transport_network,
    origins=origins,
    destinations=destinations,
    departure=datetime.datetime(2022, 2, 22, 8, 30),
    transport_modes=[
        r5py.TransportMode.TRANSIT,
        r5py.TransportMode.WALK,
    ],
    snap_to_network=True,
)

travel_times = population_grid.merge(travel_times, left_on="id", right_on="from_id")

# Display the data
print("Travel times data (first 5 rows):")
print(travel_times.head())

print(f"\nTravel time statistics:")
print(f"Min travel time: {travel_times['travel_time'].min():.1f} minutes")
print(f"Max travel time: {travel_times['travel_time'].max():.1f} minutes")
print(f"Mean travel time: {travel_times['travel_time'].mean():.1f} minutes")

# Create and save visualizations
print("\nCreating visualizations...")

# Overview map (population + railway station)
overview_map.save("overview_map.html")
print("✓ Saved overview_map.html")

# Travel times map
travel_time_map = travel_times.explore("travel_time", cmap="Greens")
travel_time_map.save("travel_times_map.html")
print("✓ Saved travel_times_map.html")
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


detailed_itineraries = r5py.DetailedItineraries(
    transport_network,
    origins=origins,
    destinations=destinations,
    departure=datetime.datetime(2022, 2, 22, 8, 30),
    transport_modes=[
        r5py.TransportMode.TRANSIT,
        r5py.TransportMode.WALK,
        #r5py.TransportMode.CAR,
        #r5py.TransportMode.BICYCLE,
    ],
    snap_to_network=True,
)

# Display the detailed itinerary data
print("Detailed itineraries data (first 5 rows):")
print(detailed_itineraries.head())

print(f"\nColumns available in DetailedItineraries:")
print(list(detailed_itineraries.columns))

# Analyze transport modes
print(f"\nTransport mode analysis:")
if 'transport_mode' in detailed_itineraries.columns:
    mode_counts = detailed_itineraries['transport_mode'].value_counts()
    print("Transport modes used:")
    for mode, count in mode_counts.items():
        print(f"  {mode}: {count} trips")

# Travel time statistics
if 'total_time' in detailed_itineraries.columns:
    print(f"\nTravel time statistics:")
    print(f"Min travel time: {detailed_itineraries['total_time'].min():.1f} minutes")
    print(f"Max travel time: {detailed_itineraries['total_time'].max():.1f} minutes")
    print(f"Mean travel time: {detailed_itineraries['total_time'].mean():.1f} minutes")

# Create and save visualizations
print("\nCreating visualizations...")

# Overview map (population + railway station)
overview_map.save("overview_map.html")
print("✓ Saved overview_map.html")

# Merge with population grid for mapping (using total_time if available)
if 'total_time' in detailed_itineraries.columns:
    travel_data = population_grid.merge(detailed_itineraries, left_on="id", right_on="from_id")
    travel_time_map = travel_data.explore("total_time", cmap="Greens")
    travel_time_map.save("detailed_itineraries_map.html")
    print("✓ Saved detailed_itineraries_map.html")
else:
    print("Note: total_time column not found - check DetailedItineraries output structure")
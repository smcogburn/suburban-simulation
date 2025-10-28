import geopandas
import r5py
import r5py.sampledata.helsinki
import shapely
import datetime
import pandas as pd
import matplotlib.pyplot as plt

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


# Run separate analyses for different transport mode combinations
# CAR and TRANSIT cannot be mixed in the same DetailedItineraries call

print("Computing transit + walk itineraries...")
transit_itineraries = r5py.DetailedItineraries(
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

print("\nComputing car itineraries...")
car_itineraries = r5py.DetailedItineraries(
    transport_network,
    origins=origins,
    destinations=destinations,
    departure=datetime.datetime(2022, 2, 22, 8, 30),
    transport_modes=[
        r5py.TransportMode.CAR,
    ],
    snap_to_network=True,
)

# Combine the results
print("\n" + "="*60)
print("TRANSIT + WALK RESULTS")
print("="*60)
print("\nDetailed itineraries data (first 5 rows):")
print(transit_itineraries.head())

print(f"\nColumns available:")
print(list(transit_itineraries.columns))

# Travel time statistics for transit
if 'travel_time' in transit_itineraries.columns:
    print(f"\nTransit travel time statistics:")
    # Convert Timedelta to minutes
    transit_times_minutes = transit_itineraries['travel_time'].dt.total_seconds() / 60
    print(f"Min travel time: {transit_times_minutes.min():.1f} minutes")
    print(f"Max travel time: {transit_times_minutes.max():.1f} minutes")
    print(f"Mean travel time: {transit_times_minutes.mean():.1f} minutes")

print("\n" + "="*60)
print("CAR RESULTS")
print("="*60)
print("\nDetailed itineraries data (first 5 rows):")
print(car_itineraries.head())

# Travel time statistics for car
if 'travel_time' in car_itineraries.columns:
    print(f"\nCar travel time statistics:")
    # Convert Timedelta to minutes
    car_times_minutes = car_itineraries['travel_time'].dt.total_seconds() / 60
    print(f"Min travel time: {car_times_minutes.min():.1f} minutes")
    print(f"Max travel time: {car_times_minutes.max():.1f} minutes")
    print(f"Mean travel time: {car_times_minutes.mean():.1f} minutes")

# Mode Share Analysis
print("\n" + "="*60)
print("MODE SHARE ANALYSIS")
print("="*60)

# Convert travel times to minutes for comparison
transit_df = transit_itineraries.copy()
transit_df['travel_time_minutes'] = transit_df['travel_time'].dt.total_seconds() / 60
transit_df['mode'] = 'transit'

car_df = car_itineraries.copy()
car_df['travel_time_minutes'] = car_df['travel_time'].dt.total_seconds() / 60
car_df['mode'] = 'car'

# Merge both datasets to compare travel times for each origin-destination pair
# Keep only the columns we need
transit_comparison = transit_df[['from_id', 'to_id', 'travel_time_minutes']].rename(
    columns={'travel_time_minutes': 'transit_time'}
)
car_comparison = car_df[['from_id', 'to_id', 'travel_time_minutes']].rename(
    columns={'travel_time_minutes': 'car_time'}
)

# Merge to get both times for each OD pair
mode_comparison = transit_comparison.merge(
    car_comparison,
    on=['from_id', 'to_id'],
    how='outer'
)

# Determine which mode would be chosen (faster travel time)
# If either mode is missing (NaN), choose the available one
mode_comparison['chosen_mode'] = mode_comparison.apply(
    lambda row: 'car' if pd.isna(row['transit_time']) else 
                ('transit' if pd.isna(row['car_time']) else
                ('car' if row['car_time'] <= row['transit_time'] else 'transit')),
    axis=1
)

mode_comparison['time_difference'] = mode_comparison['transit_time'] - mode_comparison['car_time']

# Calculate mode share statistics
mode_counts = mode_comparison['chosen_mode'].value_counts()
mode_percentages = (mode_counts / len(mode_comparison) * 100).round(1)

print("\nMode Share Results:")
print("-" * 40)
for mode, count in mode_counts.items():
    percentage = mode_percentages[mode]
    print(f"{mode.upper()}: {count} trips ({percentage}%)")

print(f"\nTotal trips analyzed: {len(mode_comparison)}")

# Travel time comparison statistics
print("\nTravel Time Comparison:")
print("-" * 40)
print(f"Average time difference (transit - car): {mode_comparison['time_difference'].mean():.1f} minutes")
print(f"Transit is faster in {(mode_comparison['time_difference'] < 0).sum()} trips")
print(f"Car is faster in {(mode_comparison['time_difference'] > 0).sum()} trips")

# Create pie chart
fig, ax = plt.subplots(figsize=(10, 6))
colors = ['#ff6b6b', '#4ecdc4']  # Red for car, teal for transit
wedges, texts, autotexts = ax.pie(
    mode_counts.values,
    labels=[f"{mode.upper()}" for mode in mode_counts.index],
    autopct='%1.1f%%',
    colors=colors,
    startangle=90,
    textprops={'fontsize': 14, 'weight': 'bold'}
)
ax.set_title('Mode Share: Car vs. Transit\n(Based on faster travel time)', 
             fontsize=16, weight='bold', pad=20)
plt.savefig('mode_share_pie_chart.png', dpi=300, bbox_inches='tight')
print("\n✓ Saved mode_share_pie_chart.png")

# Create comparison histogram
fig, ax = plt.subplots(figsize=(12, 6))
ax.hist(mode_comparison['time_difference'].dropna(), bins=30, color='#4ecdc4', alpha=0.7, edgecolor='black')
ax.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Equal travel time')
ax.set_xlabel('Time Difference (minutes): Transit - Car\n(Negative = Transit faster)', fontsize=12, weight='bold')
ax.set_ylabel('Number of Trips', fontsize=12, weight='bold')
ax.set_title('Distribution of Travel Time Differences', fontsize=14, weight='bold')
ax.legend()
ax.grid(alpha=0.3)
plt.savefig('travel_time_comparison_histogram.png', dpi=300, bbox_inches='tight')
print("✓ Saved travel_time_comparison_histogram.png")

# Create and save visualizations
print("\nCreating maps...")

# Overview map (population + railway station)
overview_map.save("overview_map.html")
print("✓ Saved overview_map.html")

# Merge mode choice data with population grid for mapping
if not mode_comparison.empty:
    # Drop geometry from mode_comparison if it exists to avoid conflicts
    mode_comparison_no_geom = mode_comparison.drop(columns=['geometry'], errors='ignore')
    
    # Merge with population grid, keeping only the geometry from population_grid
    travel_data = population_grid.merge(
        mode_comparison_no_geom, 
        left_on="id", 
        right_on="from_id",
        how='inner'
    )
    
    # Create map colored by chosen mode
    mode_map = travel_data.explore(
        column="chosen_mode",
        categorical=True,
        cmap=['#ff6b6b', '#4ecdc4'],  # Red for car, teal for transit
        legend=True,
        legend_kwds={'caption': 'Chosen Transport Mode'}
    )
    mode_map.save("mode_choice_map.html")
    print("✓ Saved mode_choice_map.html")
    
    # Create map colored by time difference
    time_diff_map = travel_data.explore(
        column="time_difference",
        cmap="RdYlGn_r",  # Red = transit slower, Green = transit faster
        legend=True,
        legend_kwds={'caption': 'Time Difference: Transit - Car (minutes)'}
    )
    time_diff_map.save("time_difference_map.html")
    print("✓ Saved time_difference_map.html")

print("\n" + "="*60)
print("Analysis complete! Check the generated files:")
print("  - mode_share_pie_chart.png")
print("  - travel_time_comparison_histogram.png") 
print("  - mode_choice_map.html")
print("  - time_difference_map.html")
print("="*60)
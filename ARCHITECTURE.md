# Suburban Simulation - System Architecture

## Project Overview
Simulating the impact of transportation policy changes on mode share in suburban areas (Columbia-Ellicott City corridor, MD).

## Goal
Estimate impact of two policy levers:
1. **Policy A**: Cutting bus headways (30min → 10min)
2. **Policy B**: Adding protected bike infrastructure (reducing LTS levels)

Measure: Change in non-car trip share via 2×2 factorial analysis (Baseline, A, B, A+B)

## Data Pipeline

### 1. Input Data
- **OSM Extract**: Road network and POIs (via OSMnx)
- **GTFS Files**: 5 MTA Maryland transit feeds
  - `mdotmta_gtfs_localbus.zip`
  - `mdotmta_gtfs_commuterbus.zip`
  - `mdotmta_gtfs_lightrail.zip`
  - `mdotmta_gtfs_marc.zip`
  - `mdotmta_gtfs_metro.zip`

### 2. Network Building
- **Tool**: r5py.TransportNetwork
- **Inputs**: OSM PBF + GTFS files + optional elevation model
- **Output**: Multimodal routing network

### 3. Trip Generation
- **Origins/Destinations**: Sample from buildings and POIs using OSMnx
- **Temporal**: Random departure times within peak hours
- **Output**: List of OD pairs with timestamps

### 4. Routing & Analysis
- **Tool**: r5py.DetailedItineraries (NOT TravelTimeMatrix)
- **Returns**: 
  - Transport modes used
  - Wait times
  - Path geometry
  - Travel times by segment
- **Transport Modes**: TRANSIT, WALK, BICYCLE, CAR (separate analyses)

### 5. Scenario Modifications
- **Baseline**: Current network as-is
- **Policy A**: Modify GTFS headways programmatically
- **Policy B**: Modify OSM/network to reduce LTS levels on target corridors
- **Policy A+B**: Apply both modifications

### 6. Mode Share Calculation
- **Method**: For each origin-destination pair, compute both car and transit travel times
- **Decision Rule**: Choose the mode with the shorter travel time
- **Outputs**: 
  - Mode share percentages (% car vs % transit)
  - Travel time differences (transit - car)
  - Spatial distribution of mode choices

### 7. Visualization & Output
- **Pie Chart**: Overall mode share (car vs. transit)
- **Histogram**: Distribution of travel time differences
- **Interactive Maps**:
  - Mode choice by origin location
  - Time difference by origin location
  - Overview map with population density
- **Statistics**: Min/max/mean travel times, mode choice breakdown

## Current Implementation Status

### ✅ Completed
- Basic r5py setup with sample Helsinki data
- Understanding of DetailedItineraries output structure
- Map visualization pipeline
- **FIXED**: CAR routing issue - now running separate analyses for CAR vs TRANSIT+WALK
- **FIXED**: Timedelta formatting issue - converting to minutes for display
- **IMPLEMENTED**: Mode share analysis - compares car vs transit travel times
- **IMPLEMENTED**: Visualizations - pie chart, histogram, and interactive maps showing mode choice

### 🚧 In Progress
- Need to switch from Helsinki sample to Columbia-Ellicott City area
- Need to download/prepare local OSM + GTFS data

### 📋 To Do
1. Define study area boundary (Columbia-Ellicott City polygon)
2. Download OSM data for study area
3. Set up building/POI sampling for OD pairs
4. Implement GTFS headway modification
5. Implement OSM LTS modification
6. Run 2×2 factorial scenarios
7. Statistical analysis and visualization
8. Mode choice logic (compare car vs transit times to determine which mode is chosen)

## Technical Architecture

### File Structure
```
suburban-simulation/
├── data/                                  # GTFS feeds and raw data
│   ├── mdotmta_gtfs_localbus.zip
│   ├── mdotmta_gtfs_commuterbus.zip
│   ├── mdotmta_gtfs_lightrail.zip
│   ├── mdotmta_gtfs_marc.zip
│   └── mdotmta_gtfs_metro.zip
├── main.py                                # Main analysis script
├── notes.md                               # Project notes
├── README.md                              # Project description
├── ARCHITECTURE.md                        # This file (master guide)
└── [Generated outputs]
    ├── mode_share_pie_chart.png           # Pie chart: car vs transit %
    ├── travel_time_comparison_histogram.png # Histogram of time differences
    ├── mode_choice_map.html               # Map colored by chosen mode
    ├── time_difference_map.html           # Map colored by time difference
    └── overview_map.html                  # Population density + destination
```

### Key Dependencies
- r5py: Multimodal routing engine
- geopandas: Spatial data handling
- OSMnx: OpenStreetMap data extraction
- pandas: Data analysis
- folium: Interactive mapping

## Resolved Issues

### 1. CAR + TRANSIT Mixing Issue ✅ FIXED
**Problem**: r5py.DetailedItineraries throws `KeyError: 193` when CAR and TRANSIT are both in transport_modes list.

**Root Cause**: r5py's internal routing tries to find transit stop access legs for CAR mode, but stop ID 193 doesn't exist in the access_legs_by_stop dictionary. This is an incompatibility in how the library handles multi-modal routing when direct driving is combined with transit.

**Solution Implemented**: Run separate analyses - one for transit+walk, another for car-only routing. This gives us two separate itinerary datasets that can be compared to determine mode choice based on travel times.

## Current Issues
None at the moment.


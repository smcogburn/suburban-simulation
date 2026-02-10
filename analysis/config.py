"""
Configuration for the suburban simulation analysis pipeline.
All constants, file paths, bounding boxes, and parameters in one place.
"""

from pathlib import Path
import datetime

# === Paths ===
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OSM_DIR = DATA_DIR / "osm"
GTFS_BASELINE_DIR = DATA_DIR / "gtfs" / "baseline"
GTFS_DOUBLED_DIR = DATA_DIR / "gtfs" / "doubled"
EXPORT_DIR = DATA_DIR / "export"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# OSM files
OSM_PBF_FULL = OSM_DIR / "maryland-260209.osm.pbf"
OSM_PBF_STUDY = OSM_DIR / "columbia-study.osm.pbf"
OSM_PBF_BIKE = OSM_DIR / "columbia-bike.osm.pbf"

# GTFS feed filenames (same names used in baseline/ and doubled/)
GTFS_FEEDS = [
    "mdotmta_gtfs_localbus.zip",
    "mdotmta_gtfs_commuterbus.zip",
    "mdotmta_gtfs_lightrail.zip",
    "mdotmta_gtfs_marc.zip",
    "mdotmta_gtfs_metro.zip",
]

# === Study Area Bounding Boxes ===

# Analysis area (larger - provides routing context beyond the viz boundary)
ANALYSIS_BBOX = {
    "west": -76.95,
    "south": 39.15,
    "east": -76.72,
    "north": 39.30,
}

# Visualization area (smaller ~10-15 km^2 focused on Columbia)
VIZ_BBOX = {
    "west": -76.90,
    "south": 39.18,
    "east": -76.80,
    "north": 39.24,
}

# Center point for coordinate projection (used by both Python export and JS viz)
VIZ_CENTER = {
    "lng": -76.85,
    "lat": 39.21,
}

# === Temporal Settings ===
DEPARTURE_DATE = datetime.date(2025, 4, 15)  # A Tuesday (typical weekday)
RUSH_START = datetime.time(7, 0)
RUSH_END = datetime.time(9, 30)

# Departure time slots (spread trips across morning rush)
DEPARTURE_SLOTS = [
    datetime.time(7, 0),
    datetime.time(7, 30),
    datetime.time(8, 0),
    datetime.time(8, 30),
    datetime.time(9, 0),
]

# === Origin-Destination Generation ===
NUM_ORIGINS = 200          # Residential sample points
NUM_DESTINATIONS = 30      # Employment/commercial sample points
VIZ_TRIP_SUBSET = 500      # Number of OD pairs for DetailedItineraries (viz paths)

# === BPR Congestion Parameters ===
# Bureau of Public Roads volume-delay function:
# congested_time = free_flow_time * (1 + ALPHA * (volume / capacity) ^ BETA)
BPR_ALPHA = 0.15
BPR_BETA = 4.0

# Road capacity estimates (vehicles per lane per hour, one direction)
CAPACITY_PER_LANE = {
    "motorway": 2000,
    "motorway_link": 1800,
    "trunk": 1800,
    "trunk_link": 1600,
    "primary": 1800,
    "primary_link": 1600,
    "secondary": 1600,
    "secondary_link": 1400,
    "tertiary": 1400,
    "tertiary_link": 1200,
    "residential": 1000,
    "unclassified": 1000,
    "living_street": 600,
}

# Default lane counts when OSM data is missing
DEFAULT_LANES = {
    "motorway": 3,
    "motorway_link": 1,
    "trunk": 2,
    "trunk_link": 1,
    "primary": 2,
    "primary_link": 1,
    "secondary": 2,
    "secondary_link": 1,
    "tertiary": 1,
    "tertiary_link": 1,
    "residential": 1,
    "unclassified": 1,
    "living_street": 1,
}

# Scale factor: each synthetic trip represents this many real trips
# (makes congestion patterns visible with limited sample size)
TRIP_SCALE_FACTOR = 50

# === Congestion Time Windows (seconds since 7:00 AM) ===
TIME_WINDOWS = [
    {"start": 0, "end": 1800, "label": "7:00-7:30"},
    {"start": 1800, "end": 3600, "label": "7:30-8:00"},
    {"start": 3600, "end": 5400, "label": "8:00-8:30"},
    {"start": 5400, "end": 7200, "label": "8:30-9:00"},
    {"start": 7200, "end": 9000, "label": "9:00-9:30"},
]

# === Scenario Definitions ===
SCENARIOS = {
    "baseline": {
        "label": "Baseline",
        "description": "Current transit network, no bike infrastructure changes",
        "osm_pbf": OSM_PBF_STUDY,
        "gtfs_dir": GTFS_BASELINE_DIR,
        "include_bike": False,
    },
    "policy_a": {
        "label": "Policy A: Doubled Bus Frequency",
        "description": "Bus headways halved across local bus network",
        "osm_pbf": OSM_PBF_STUDY,
        "gtfs_dir": GTFS_DOUBLED_DIR,
        "include_bike": False,
    },
    "policy_b": {
        "label": "Policy B: Protected Bike Lanes",
        "description": "Protected bike lanes on arterial roads (LTS reduced to 2)",
        "osm_pbf": OSM_PBF_BIKE,
        "gtfs_dir": GTFS_BASELINE_DIR,
        "include_bike": True,
    },
    "policy_ab": {
        "label": "Both Policies",
        "description": "Doubled bus frequency + protected bike lanes combined",
        "osm_pbf": OSM_PBF_BIKE,
        "gtfs_dir": GTFS_DOUBLED_DIR,
        "include_bike": True,
    },
}

# === Visualization Colors (used in export metadata) ===
MODE_COLORS = {
    "CAR": "#ff4444",
    "TRANSIT": "#4488ff",
    "WALK": "#ffcc00",
    "BICYCLE": "#44ff88",
}

# === Policy B: Roads to add bike lanes to ===
BIKE_LANE_HIGHWAY_TYPES = {
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
}

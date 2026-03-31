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
OSM_PBF_FULL = OSM_DIR / "maryland-260309.osm.pbf"
OSM_PBF_STUDY = OSM_DIR / "clipped.osm.pbf"
OSM_PBF_BIKE = OSM_DIR / "columbia-bike.osm.pbf"

# GTFS feed filenames (same names used in baseline/ and doubled/)
GTFS_FEEDS = [
    "aac_gtfs.zip",                      # Anne Arundel County buses (Annapolis/Crofton/Edgewater)
    "princegeorgescounty-md-us.zip",     # PG County TheBus (Bowie/Largo/Upper Marlboro)
    "mdotmta_gtfs_localbus.zip",         # MTA Maryland local bus (regional — clipped to corridor)
    "mdotmta_gtfs_commuterbus.zip",      # MTA commuter express
    "mdotmta_gtfs_lightrail.zip",        # MTA Light Rail
    "mdotmta_gtfs_marc.zip",             # MARC commuter rail (Penn/Camden lines)
    # mdotmta_gtfs_metro.zip excluded — Metro Green/Orange lines don't reach the study area
    # (0 trips survive bbox+window filter). Confirmed by clip_gtfs.py.
]

# === Study Area Bounding Boxes ===

# Analysis area (Bowie / Crofton / Annapolis corridor)
ANALYSIS_BBOX = {
    "west": -76.90,
    "south": 38.87,
    "east": -76.42,
    "north": 39.10,
}

# Visualization area (full Bowie→Annapolis corridor for 3D flyover)
VIZ_BBOX = {
    "west": -76.90,
    "south": 38.87,
    "east": -76.42,
    "north": 39.10,
}

# Center point for coordinate projection (used by both Python export and JS viz)
VIZ_CENTER = {
    "lng": -76.66,
    "lat": 38.985,
}

# === Temporal Settings ===
DEPARTURE_DATE = datetime.date(2025, 9, 16)  # A Tuesday within GTFS service period (starts 2025-06-15)
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
NUM_ORIGINS = 200                  # Residential sample points
NUM_DESTINATIONS = 30              # Total destination points (legacy, not used directly)
NUM_REGIONAL_DESTINATIONS = 9     # Major employment/commercial — full corridor (commute trips)
NUM_LOCAL_DESTINATIONS = 150      # Local POIs sampled corridor-wide; proximity-filtered per origin
LOCAL_TRIP_RADIUS_KM = 5.0        # Max distance (km) for a "local" trip to be included
VIZ_TRIP_SUBSET = 500             # Number of OD pairs for DetailedItineraries (viz paths)

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

# Scale factor: each synthetic trip represents this many real trips.
# DetailedItineraries uses 20 sampled origins out of 200 total (10x undersample).
# Additionally, 200 synthetic origins represent a much larger real population.
# 500 = 10 (sampling ratio) × 50 (population scale) — keeps road V/C ratios
# in the 0.6-1.2 range during peak, producing visible BPR congestion effects.
TRIP_SCALE_FACTOR = 500

# === Congestion Time Windows (seconds since 7:00 AM) ===
# 5-minute windows (300s each) over the 2.5-hour rush period = 30 windows.
# Finer granularity keeps BPR accurate and reduces JS interpolation artifacts.
TIME_WINDOWS = [
    {"start": i * 300, "end": (i + 1) * 300,
     "label": f"{7 + (i * 5) // 60}:{(i * 5) % 60:02d}-{7 + ((i + 1) * 5) // 60}:{((i + 1) * 5) % 60:02d}"}
    for i in range(30)
]

# === Scenario Definitions ===
SCENARIOS = {
    "baseline": {
        "label": "Baseline",
        "description": "Current transit network, no bike infrastructure changes",
        "osm_pbf": OSM_PBF_STUDY,
        "gtfs_dir": GTFS_BASELINE_DIR,
        "include_bike": True,
        "bike_max_lts": 3,  # No protected lanes — cyclists avoid arterials (LTS 4)
    },
    "policy_a": {
        "label": "Policy A: 5-Minute Bus Frequency",
        "description": "Bus headways reduced to 5 minutes across local bus network",
        "osm_pbf": OSM_PBF_STUDY,
        "gtfs_dir": GTFS_DOUBLED_DIR,
        "include_bike": True,
        "bike_max_lts": 3,  # No bike infrastructure change
    },
    "policy_b": {
        "label": "Policy B: Protected Bike Lanes",
        "description": "Protected bike lanes on arterial roads — cyclists can use arterials directly",
        "osm_pbf": OSM_PBF_BIKE,
        "gtfs_dir": GTFS_BASELINE_DIR,
        "include_bike": True,
        "bike_max_lts": 4,  # Protected lanes make arterials accessible — LTS cap raised to 4.
                            # R5 does not reliably use cycleway=track to lower LTS on parent ways;
                            # instead the cap directly models "these roads are now safe to use."
                            # The OSM modification (cycleway=track) is kept for completeness.
    },
    "policy_ab": {
        "label": "Both Policies",
        "description": "Doubled bus frequency + protected bike lanes combined",
        "osm_pbf": OSM_PBF_BIKE,
        "gtfs_dir": GTFS_DOUBLED_DIR,
        "include_bike": True,
        "bike_max_lts": 4,  # Same as Policy B — arterials accessible
    },
}

# === Mode Choice Generalized Cost Parameters ===
MODE_CHOICE = {
    "car_bpr_factor": 1.0,       # first-pass: free-flow (BPR ratio applied in second pass after congestion is computed)
    "car_penalty_min": 8,        # parking search + walk from lot to destination. Suburban typical: 5-12 min.
                                 # Standard practice in mode choice models — car door-to-door time
                                 # includes finding/paying for parking + egress walk. Omitting it
                                 # systematically under-prices car vs transit/bike, causing near-0% transit.
    "transit_ivt_factor": 0.85,  # productive in-vehicle time discount (riders can read/work)
    "bike_ivt_factor": 1.15,     # physical effort penalty
    "walk_ivt_factor": 1.4,      # standard transport research effort penalty
    "noise_std_min": 15,         # std dev of individual preference variation (minutes).
                                 # 15 min reflects unobserved heterogeneity: car-free households,
                                 # cycling enthusiasts, transit preferences, captive riders.
                                 # Standard range in suburban discrete choice models is 8-15 min;
                                 # using upper bound to capture latent demand in a car-dependent area.
}

# Maximum bicycle traffic stress level for routing.
# LTS 1 = protected lanes only (very conservative)
# LTS 2 = protected lanes + quiet streets (r5py default, too strict for baseline)
# LTS 3 = includes unprotected arterials (what typical cyclists actually use)
# LTS 4 = all roads including highways (unrealistic)
# Baseline uses LTS 3 so that cycling is physically possible on the existing network.
# Policy B OSM file sets arterials to LTS 2, meaning those roads become "preferred"
# routes and bike times drop significantly on the improved network.
BIKE_MAX_LTS_BASELINE = 3  # LTS 3 = confident cyclist on secondary roads.
                           # Arterials (LTS 4) are excluded in baseline → circuitous detours.
                           # Policy B tags arterials as cycleway=track → r5py computes LTS 1-2
                           # → they become included at max_lts=3 → direct routes available.
                           # Both scenarios use this same cap; the OSM change drives the shift.
                           # BIKE_MAX_LTS_POLICY was removed — it was defined but never used.

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

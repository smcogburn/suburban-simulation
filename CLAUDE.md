# Suburban Simulation - Project Guide

## What This Is
STEM senior thesis project: "Designing Better Suburbs: Simulating the Impact of Urban Planning Strategies on Quality of Life." Studying how two policy interventions (doubling bus frequency + adding protected bike lanes) affect transportation mode share in suburban Columbia-Ellicott City, MD.

## Architecture
Three layers connected by JSON files:
1. **Analysis pipeline** (Python, `analysis/`) — r5py routing, mode share calculation, BPR congestion model
2. **Data export** (`data/export/`) — JSON files (roads, buildings, trips, congestion, metadata)
3. **3D Visualization** (Three.js, `visualization/`) — web-based animated trip replay

## Two-Machine Workflow
- **MacBook Air (8GB)** — Code editing, Three.js visualization, symposium presentation
- **Windows Desktop (16GB, WSL)** — Heavy analysis: r5py routing, GTFS/OSM modification, all 4 scenarios
- **Bridge:** Git push/pull. Analysis outputs JSON to `data/export/`, viz reads it.
- Large data files (PBF, GTFS zips) are gitignored — copy them to Windows once manually.

## Key Commands
```bash
# === On Windows/WSL (analysis) ===

# Install dependencies (including pyosmium which needs Linux)
pip install -r analysis/requirements.txt
sudo apt install osmium-tool   # For PBF clipping

# Clip Maryland PBF to study area
osmium extract -b -76.95,39.15,-76.72,39.30 data/osm/maryland-260209.osm.pbf -o data/osm/columbia-study.osm.pbf

# Build policy scenario data (modify GTFS headways + OSM bike lanes)
python -m analysis.scenario_builder

# Run the full analysis pipeline
python -m analysis.run_pipeline

# Run just data prep (extract buildings/roads, no routing)
python -m analysis.run_pipeline --prep-only

# Run a single scenario
python -m analysis.run_pipeline --scenario baseline

# Skip slow DetailedItineraries (no viz paths, just mode share stats)
python -m analysis.run_pipeline --skip-detailed

# === On MacBook (visualization) ===

# Serve the visualization locally
python3 -m http.server 8000 --directory visualization/
```

## Study Area
- **Analysis area** (routing): W:-76.95, S:39.15, E:-76.72, N:39.30
- **Visualization area** (3D view): W:-76.90, S:39.18, E:-76.80, N:39.24
- Center: (-76.85, 39.21) — Columbia, MD

## 2x2 Factorial Scenarios
| Scenario | GTFS | OSM | Bike? |
|----------|------|-----|-------|
| Baseline | original | original | No |
| Policy A | doubled frequency | original | No |
| Policy B | original | bike lanes (LTS=2) | Yes |
| Both | doubled frequency | bike lanes (LTS=2) | Yes |

## Data Sources
- **OSM**: `data/osm/maryland-260209.osm.pbf` (Geofabrik MD extract)
- **GTFS**: 5 MTA Maryland feeds in `data/gtfs/baseline/`
- Clipped PBF goes to `data/osm/columbia-study.osm.pbf`

## Python Dependencies
`pip install -r analysis/requirements.txt`
Key: r5py, geopandas, osmnx, shapely, pandas, matplotlib, folium, gtfs-kit, pyosmium, tqdm

## File Structure
```
analysis/          Python analysis pipeline
  config.py        All constants and paths
  data_prep.py     OSM clipping, building/road extraction
  od_generation.py Origin-destination pair generation
  routing.py       r5py TravelTimeMatrix + DetailedItineraries
  congestion.py    BPR volume-delay congestion model
  exporter.py      Results -> JSON for visualization
  scenario_builder.py  GTFS headway + OSM LTS modifications
  run_pipeline.py  Master script

visualization/     Three.js web viewer
  index.html       Single entry point
  js/              JavaScript modules
  css/             Styles
  lib/             Vendored Three.js + OrbitControls

data/
  osm/             OSM PBF files
  gtfs/baseline/   Original GTFS feeds
  gtfs/doubled/    Modified GTFS (Policy A)
  export/          JSON bridge -> visualization
```

## Technical Notes
- r5py CAR and TRANSIT modes must be run in SEPARATE DetailedItineraries calls (mixing causes KeyError)
- Hybrid routing: TravelTimeMatrix (fast) for stats, DetailedItineraries (slow) for viz paths only
- BPR formula: congested_time = free_flow * (1 + 0.15 * (volume/capacity)^4)
- Trip scale factor: each synthetic trip represents ~50 real trips
- pyosmium only installs on Linux/WSL — use the Windows desktop for Policy B OSM modification
- Python 3.11, MacBook arm64 / Windows WSL x86_64

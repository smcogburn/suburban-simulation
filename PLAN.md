# Suburban Simulation — Project Plan & Current Status

## Overview

STEM senior thesis: "Designing Better Suburbs: Simulating the Impact of Urban Planning Strategies on Quality of Life."

The project studies how two policy interventions affect transportation mode share in suburban Columbia-Ellicott City, MD:
- **Policy A:** Double bus frequency (halve GTFS headways)
- **Policy B:** Add protected bike lanes (set LTS=2 on arterial roads in OSM)

Tested as a 2×2 factorial: Baseline, A only, B only, A+B combined.

---

## Architecture (Three Layers)

```
┌─────────────────────────┐
│  1. Analysis Pipeline    │  Python (r5py, geopandas, pyrosm)
│     Runs on Windows/WSL  │  Computes travel times, mode share, congestion
│     16GB RAM             │
└──────────┬──────────────┘
           │ outputs JSON files
           ▼
┌─────────────────────────┐
│  2. Data Export          │  JSON files in data/export/
│     (the bridge)         │  roads.json, buildings.json, trips_*.json, congestion_*.json
└──────────┬──────────────┘
           │ read by
           ▼
┌─────────────────────────┐
│  3. 3D Visualization     │  Three.js (browser-based)
│     Runs anywhere        │  Animated trip replay with buildings, roads, congestion
│     Presented at sympos. │  Camera controls, cinematic idle mode
└─────────────────────────┘
```

**Two-machine workflow:**
- **MacBook Air (8GB, arm64)** — Code editing, Three.js visualization, symposium presentation
- **Windows Desktop (16GB, WSL)** — Heavy analysis: r5py routing, GTFS/OSM modification
- **Bridge:** Git push/pull. Large data files (PBF, GTFS zips) are gitignored — copy manually.

---

## What's Been Built So Far

### Analysis Pipeline (Python) — ALL FILES WRITTEN, NONE TESTED YET

| File | Purpose |
|------|---------|
| `analysis/__init__.py` | Package init |
| `analysis/config.py` | All constants, paths, bounding boxes, BPR params, scenario definitions |
| `analysis/data_prep.py` | OSM clipping (osmium, needs WSL) + building/road extraction (pyrosm) |
| `analysis/od_generation.py` | Generate origins (residential buildings), destinations (commercial), OD matrix with departure times |
| `analysis/routing.py` | r5py wrapper — TravelTimeMatrix (fast, full OD) + DetailedItineraries (slow, viz subset). Mode choice logic. |
| `analysis/congestion.py` | BPR volume-delay function. Maps trips to road segments, computes congestion ratios per time window. |
| `analysis/exporter.py` | Converts itineraries → JSON for Three.js (trips per scenario, metadata) |
| `analysis/scenario_builder.py` | Policy A: inserts interpolated GTFS trips to double frequency. Policy B: adds cycleway+lts tags to OSM PBF via pyosmium. |
| `analysis/run_pipeline.py` | Master script — runs all 4 scenarios end-to-end. Supports `--scenario`, `--skip-detailed`, `--prep-only` flags. |
| `analysis/requirements.txt` | Python deps (r5py, geopandas, osmnx, pyrosm, pyosmium, etc.) |

### Visualization (Three.js) — SKELETON ONLY

| File | Status |
|------|--------|
| `visualization/index.html` | Written — HTML structure with UI panels (time slider, scenario buttons, stats overlay) |
| `visualization/css/style.css` | Written — Dark theme, all UI styling done |
| `visualization/lib/three.module.js` | Downloaded — Three.js r170 ES module |
| `visualization/lib/OrbitControls.js` | Downloaded — Camera pan/rotate/zoom |
| `visualization/lib/BufferGeometryUtils.js` | Downloaded — Geometry merging for performance |
| `visualization/js/main.js` | **NOT YET WRITTEN** |
| `visualization/js/SceneManager.js` | **NOT YET WRITTEN** |
| `visualization/js/RoadNetwork.js` | **NOT YET WRITTEN** |
| `visualization/js/Buildings.js` | **NOT YET WRITTEN** |
| `visualization/js/AgentSystem.js` | **NOT YET WRITTEN** |
| `visualization/js/TimeController.js` | **NOT YET WRITTEN** |
| `visualization/js/ScenarioPanel.js` | **NOT YET WRITTEN** |
| `visualization/js/CinematicCamera.js` | **NOT YET WRITTEN** |
| `visualization/js/DataLoader.js` | **NOT YET WRITTEN** |

### Other Files

| File | Status |
|------|--------|
| `CLAUDE.md` | Written — Project guide for Claude Code (two-machine workflow, commands, notes) |
| `.gitignore` | Updated — Ignores PBF, GTFS zips, JSON exports, generated outputs |
| `main.py` | Original Helsinki prototype — kept as reference, not part of new pipeline |
| `ARCHITECTURE.md` | Old architecture doc — still has useful context but partially outdated |

### Data Files (gitignored, must be copied to each machine manually)

| File | Location | Status |
|------|----------|--------|
| `data/osm/maryland-260209.osm.pbf` | 208.6 MB | On MacBook. Copy to Windows. |
| `data/gtfs/baseline/mdotmta_gtfs_localbus.zip` | 12.5 MB | On MacBook. Copy to Windows. |
| `data/gtfs/baseline/mdotmta_gtfs_commuterbus.zip` | 1.6 MB | On MacBook. Copy to Windows. |
| `data/gtfs/baseline/mdotmta_gtfs_lightrail.zip` | 891 KB | On MacBook. Copy to Windows. |
| `data/gtfs/baseline/mdotmta_gtfs_marc.zip` | 193 KB | On MacBook. Copy to Windows. |
| `data/gtfs/baseline/mdotmta_gtfs_metro.zip` | 56 KB | On MacBook. Copy to Windows. |
| `data/osm/columbia-study.osm.pbf` | NOT YET CREATED | Created by `osmium extract` on Windows |
| `data/osm/columbia-bike.osm.pbf` | NOT YET CREATED | Created by `scenario_builder.py` on Windows |
| `data/export/*.json` | NOT YET CREATED | Created by `run_pipeline.py` on Windows |

---

## Phase 1: Analysis Pipeline (run on Windows/WSL)

### Step 1: Setup on Windows

```bash
# Clone the repo
git clone <your-repo-url>
cd suburban-simulation

# Install Python dependencies
pip install -r analysis/requirements.txt

# Install osmium-tool for PBF clipping
sudo apt install osmium-tool
```

Copy the data files to the Windows machine:
- `data/osm/maryland-260209.osm.pbf`
- All 5 GTFS zips into `data/gtfs/baseline/`

### Step 2: Clip OSM data

```bash
osmium extract -b -76.95,39.15,-76.72,39.30 data/osm/maryland-260209.osm.pbf -o data/osm/columbia-study.osm.pbf
```

### Step 3: Test data prep (extract buildings + roads to JSON)

```bash
python -m analysis.data_prep --step extract
# Should produce: data/export/buildings.json and data/export/roads.json
```

### Step 4: Build policy scenario data

```bash
python -m analysis.scenario_builder
# Produces: data/gtfs/doubled/ (Policy A) and data/osm/columbia-bike.osm.pbf (Policy B)
```

### Step 5: Run full analysis pipeline

```bash
# Start with just baseline to test
python -m analysis.run_pipeline --scenario baseline

# If that works, run all 4 scenarios
python -m analysis.run_pipeline

# If DetailedItineraries is too slow, skip it for now (still gets mode share stats)
python -m analysis.run_pipeline --skip-detailed
```

### Step 6: Commit JSON exports, push to GitHub

The JSON files in `data/export/` need to be un-gitignored or committed separately so the MacBook can access them for visualization. Update `.gitignore` to allow `data/export/*.json`, then:

```bash
git add data/export/*.json
git commit -m "Add analysis export data for visualization"
git push
```

---

## Phase 2: 3D Visualization (Three.js)

### What needs to be built (JS modules)

All files go in `visualization/js/`. The HTML and CSS are already done.

| Module | Responsibility |
|--------|----------------|
| `DataLoader.js` | Fetch JSON files from `data/export/`, cache them, provide `preloadAll()` |
| `SceneManager.js` | Three.js scene, camera, renderer, lighting setup. Dark ground plane. |
| `Buildings.js` | Load `buildings.json`, extrude polygons as cubes, merge into single BufferGeometry |
| `RoadNetwork.js` | Load `roads.json`, render as flat geometry with vertex colors for congestion |
| `AgentSystem.js` | Animated trip dots — pool of ~500 sprites, interpolate position along path per frame |
| `TimeController.js` | Time slider (7:00-9:30 AM), play/pause, speed control, wires to agent system + congestion |
| `ScenarioPanel.js` | 4 buttons to switch scenarios, swaps trip + congestion data |
| `CinematicCamera.js` | Auto-orbit idle camera when no user input for 10 seconds |
| `main.js` | Entry point — initializes everything, runs render loop |

### Key technical details for the viz

**Coordinate projection** (WGS84 → Three.js):
```javascript
const CENTER = [-76.85, 39.21];
const SCALE = 100000;
function project(lng, lat) {
    const x = (lng - CENTER[0]) * Math.cos(CENTER[1] * Math.PI / 180) * SCALE;
    const y = (lat - CENTER[1]) * SCALE;
    return [x, y]; // x = east-west, y = north-south
}
```

**Performance rules:**
- Merge ALL building geometry into ONE mesh (single draw call)
- Merge ALL road geometry into ONE mesh with vertex colors
- Pre-allocate sprite pool for agents (don't create/destroy per frame)
- Target: 30+ FPS on MacBook Air

**Visual style:**
- Dark background (0x0a0a14), dark buildings (0x2a2a3e), no map tiles
- Roads colored by congestion: green (1.0x) → yellow (1.5x) → red (2.0x+)
- Agent dots: glowing sprites colored by mode (red=car, blue=transit, yellow=walk, green=bike)
- Time slider at bottom, scenario buttons top-right, mode share stats top-left

---

## Phase 3: Integration & Symposium Prep

- End-to-end test: pipeline → JSON → visualization
- Offline mode verification (no internet needed)
- Cinematic camera mode for idle state during presentation
- `F` key for fullscreen
- Record fallback video in case of hardware issues
- Export thesis figures (matplotlib charts) from `outputs/`

---

## Data Format Spec (JSON bridge between Python and JS)

### `metadata.json`
Study area center/bbox, time range (7:00-9:30 AM = 0-9000 seconds), scenario labels, mode colors, aggregate mode share stats per scenario.

### `roads.json`
```json
{ "segments": [
    { "id": "seg_0", "coords": [[lng,lat],...], "highway": "primary",
      "lanes": 2, "name": "...", "length_m": 245, "capacity_per_hour": 3600,
      "free_flow_speed_kmh": 56 }
]}
```

### `buildings.json`
```json
{ "features": [
    { "coords": [[lng,lat],...], "height": 9 }
]}
```

### `trips_<scenario>.json`
```json
{ "trips": [
    { "id": "t_0", "mode": "CAR", "departure": 5400, "duration": 840,
      "path": [[lng,lat],...] }
]}
```
- `departure`: seconds since 7:00 AM
- `path`: simplified waypoints along the route

### `congestion_<scenario>.json`
```json
{ "time_windows": [...],
  "data": { "seg_0": [1.0, 1.02, 1.15, 1.08, 1.01] } }
```
5 values per segment = congestion ratio per 30-min window. 1.0 = free flow.

---

## Risk & Fallback Plan

| Priority | If time is short... |
|----------|-------------------|
| 1 (MUST) | Analysis pipeline with charts/maps = the thesis |
| 2 (SHOULD) | Congestion layer + JSON export |
| 3 (NICE) | 3D viz with roads + buildings |
| 4 (STRETCH) | Animated agents, cinematic camera, polished UI |

The analysis pipeline alone with matplotlib charts and folium maps is a complete, defensible thesis. The 3D visualization is the presentation wow-factor built on top.

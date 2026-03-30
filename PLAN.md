# Suburban Simulation — Current State & Plan
*Last updated: 2026-03-29*

## What This Project Is

STEM senior thesis: "Designing Better Suburbs: Simulating the Impact of Urban Planning Strategies on Quality of Life."

Studies how two policy interventions affect transportation mode share in the **Annapolis / Bowie / Crofton corridor** of Maryland.

| Policy | What it does |
|--------|-------------|
| Baseline | Existing network, no changes |
| Policy A | 5-minute bus headways across the local network |
| Policy B | Protected bike lanes on arterials (LTS=2 in OSM) |
| Both | A + B combined |

---

## Study Area (CURRENT — updated from Columbia)

**The study area was moved from Columbia-Ellicott City to the Annapolis/Bowie/Crofton corridor.**

```
ANALYSIS_BBOX: W:-76.90, S:38.87, E:-76.42, N:39.10
VIZ_BBOX:      W:-76.90, S:38.87, E:-76.42, N:39.10
Center:        (-76.66, 38.985)
```

Covers: Bowie (PG County), Crofton (AAC), Odenton, Annapolis, Edgewater.

The OSM PBF (`data/osm/clipped.osm.pbf`) was re-clipped to these bounds using:
```bash
osmium extract -b -76.90,38.87,-76.42,39.10 data/osm/maryland-260309.osm.pbf -o data/osm/clipped.osm.pbf --overwrite
```

---

## Architecture

```
Analysis Pipeline (Python) → JSON exports → 3D Visualization (Three.js)
```

**Two-machine workflow:**
- **Windows Desktop (16GB)** — r5py routing, osmium PBF clipping, all analysis
- **MacBook Air (8GB)** — Three.js visualization, symposium presentation
- **Bridge:** Git push/pull. Large files are gitignored (PBF, GTFS zips).

---

## Current Status: WHAT IS DONE

### ✅ Analysis Pipeline (all working)

| File | Status |
|------|--------|
| `config.py` | Complete — all params tuned, see key settings below |
| `data_prep.py` | Working — extracts buildings/roads via osmnx |
| `od_generation.py` | Working — proximity-based OD matrix (local + commute trips) |
| `routing.py` | Working — TravelTimeMatrix + DetailedItineraries, generalized cost mode choice |
| `congestion.py` | Working — dynamic 2-pass BPR, 30×5-min time windows |
| `exporter.py` | Working — exports trips/congestion/metadata JSON |
| `scenario_builder.py` | Written — builds Policy A (5-min headways) and Policy B (OSM bike lanes) |
| `run_pipeline.py` | Working — skip buildings if exist, 20-origin DetailedItineraries cap |
| `export_transit_routes.py` | Working — exports GTFS shapes for visualization overlay |

### ✅ Visualization (Three.js — fully working)

All JS modules written and working:
- `SceneManager.js` — Three.js scene, full corridor scale (camera far=200000)
- `RoadNetwork.js` — roads with live congestion coloring (30 windows, backward interpolation)
- `AgentSystem.js` — trip agents, per-mode x-ray filter, live counts
- `Buildings.js` — building footprints
- `TimeController.js` — play/pause/speed
- `ScenarioPanel.js` — scenario switching
- `CinematicCamera.js` — idle cinematic mode (needs new shot coordinates for Annapolis corridor)
- `TransitLayer.js` — GTFS route overlay (visible in transit x-ray mode)
- `DataLoader.js` — JSON fetching and caching
- `main.js` — render loop, x-ray click handlers, live mode count display

### ✅ Data Available

| File | Size | Notes |
|------|------|-------|
| `data/export/buildings.json` | 71 MB | Annapolis/Bowie corridor buildings |
| `data/export/roads.json` | 19 MB | Road network with capacities |
| `data/export/trips_baseline.json` | 8 MB | Baseline trip paths (20 origins × all dests) |
| `data/export/congestion_baseline.json` | 10 MB | 30-window BPR congestion |
| `data/export/metadata.json` | 1 KB | Mode share stats |
| `data/export/transit_routes.json` | TBD | GTFS route shapes for overlay |

### ✅ GTFS Feeds (in `data/gtfs/baseline/`)

| Feed | Stops in area | Notes |
|------|--------------|-------|
| `aac_gtfs.zip` | 158 | Anne Arundel County buses (Crofton, Annapolis, Edgewater). Calendar fixed to 2020-2026. shapes.txt empty — reconstructed from stop sequences. |
| `princegeorgescounty-md-us.zip` | 615 | PG County TheBus (Bowie, Largo, Upper Marlboro). Calendar fixed to 2024-2027. |
| `mdotmta_gtfs_localbus.zip` | regional | MTA Maryland local bus |
| `mdotmta_gtfs_commuterbus.zip` | regional | MTA commuter express |
| `mdotmta_gtfs_lightrail.zip` | few | Light Rail |
| `mdotmta_gtfs_marc.zip` | few | MARC commuter rail |
| `mdotmta_gtfs_metro.zip` | few | Metro Green/Orange line |

---

## Key Config Parameters (current values)

```python
# Departure date — within ALL GTFS service periods
DEPARTURE_DATE = datetime.date(2025, 9, 16)  # Tuesday

# OD generation
NUM_ORIGINS = 200
NUM_REGIONAL_DESTINATIONS = 9    # employment centers, all-to-all (commute trips)
NUM_LOCAL_DESTINATIONS = 150     # local POIs, proximity-filtered at 5km radius
LOCAL_TRIP_RADIUS_KM = 5.0

# Mode choice (generalized cost)
noise_std_min = 12               # individual preference variation (was 5, too low)
transit_ivt_factor = 0.85        # productive transit time discount
bike_ivt_factor = 1.15           # cycling effort penalty
car_bpr_factor = 1.0             # free-flow first pass, BPR applied second pass

# Bike routing
BIKE_MAX_LTS_BASELINE = 3        # allows arterials cyclists actually use
                                 # Policy B OSM tags lanes as LTS 2 → faster routes

# Congestion: 30 × 5-minute windows (was 10 × 15-min, was 5 × 30-min)
TIME_WINDOWS = [i*300 to (i+1)*300 for i in range(30)]

# Visualization subset
VIZ_DET_ORIGINS = 20             # origins for DetailedItineraries (20 × all dests ≈ 600 pairs/mode)
                                 # was "all unique origins from viz_subset" = memory bomb (crashed machine)

# JVM heap cap (prevents r5py from consuming all RAM)
JAVA_TOOL_OPTIONS = "-Xmx10g"
```

---

## Bugs Fixed (complete list)

| Bug | Fix |
|-----|-----|
| GTFS date outside service period (Apr 2025 before Jun 2025 start) | Changed DEPARTURE_DATE to Sep 16 2025 |
| 100% car — "pick fastest mode" ignored transit/bike | Generalized cost model with noise |
| Bike excluded from baseline/policy_a | `include_bike: True` for all 4 scenarios |
| BPR fixed at 1.2× regardless of traffic | Dynamic 2-pass BPR from actual traffic counts |
| 30-min congestion windows too coarse | 10×15min → 30×5min windows |
| Road colors only updated on window change (not during playback) | `applyCongestion` called every 15 sim-seconds in animate loop |
| Road colors updating every frame → GPU upload lag + flickering | Throttled to ≥15 sim-second change threshold |
| `depthWrite: false` on roads causing flicker | Reverted; kept elevated road Y coords instead |
| Road z-fighting with ground plane | Raised all ROAD_Y values (residential: 0→1, motorway: 3→6) |
| Backward interpolation so roads don't anticipate future congestion | Changed JS to lerp(prev_window → current_window) |
| Stray agents (2-point routing failures = straight lines) | Filter `path.length < 3` |
| Local OD pairs not actually local (grocery 20km from origin) | Proximity-based OD matrix: each origin only paired with POIs within 5km |
| DetailedItineraries memory bomb (200 origins × 30 dests × 3 modes) | Fixed to 20 sampled origins — was crashing 16GB machine |
| JVM heap uncapped → consumes all RAM + 40GB swap → freeze | `JAVA_TOOL_OPTIONS=-Xmx10g` |
| OSM PBF covering old Columbia area, not Annapolis/Bowie | Re-clipped to new bbox |
| Capacity divided by 2 for 30-min windows (now 5-min) | Dynamic: `capacity_per_hour × window_hours` |
| `[1.0] * 5` hardcoded for 10-window system | `[1.0] * len(TIME_WINDOWS)` |
| Buildings/roads re-extracted on every pipeline run | Skip if files exist; `--force-prep` to override |
| Bike LTS too strict (LTS≤2 = almost no routes in baseline) | `max_bicycle_traffic_stress=3` in baseline |
| AAC GTFS calendar expired (ended 2023-12-31) | Extended to 2026-12-31 |
| PG County GTFS calendar not started yet (starts 2025-12-15) | Moved start to 2024-01-01 |
| AAC shapes.txt empty (no route geometry) | Reconstruct from stop sequences in export_transit_routes.py |
| Missing local transit: no AAC or PG County feeds | Added both feeds — 773 additional stops in study area |
| Transit 0% — no local buses in OD pairs | Above GTFS fixes; multimodal (walk+transit+walk) already working |

---

## What Still Needs to Be Done

### Immediate (before symposium)

- [ ] **Run `python -m analysis.export_transit_routes`** — generates transit_routes.json for viz overlay
- [ ] **Re-run baseline** with all fixes: `python -m analysis.run_pipeline --scenario baseline`
  - Expected: bike ~5-12% (LTS 3 + noise_std=12), transit >0% (AAC + PG County feeds)
- [ ] **Run scenario_builder.py** — builds Policy A GTFS + Policy B OSM
- [ ] **Run full pipeline** — all 4 scenarios: `python -m analysis.run_pipeline`
- [ ] **Push JSON exports** to GitHub so MacBook can pull for presentation

### Visual Polish (low priority, do after pipeline works)

- [ ] CinematicCamera.js — update shot coordinates for Annapolis/Bowie corridor (old shots aimed at downtown Annapolis which is now off-center)
- [ ] Neighborhood labels — update positions and names for new study area
- [ ] Building contrast — currently hard to see (gray blobs); could increase emissive brightness

### Thesis / Presentation

- [ ] Verify mode share numbers make sense across 4 scenarios
- [ ] Generate matplotlib comparison charts from metadata.json stats
- [ ] Prepare talking points for each scenario comparison
- [ ] Test offline (no internet) — visualization reads local JSON, should work

---

## How to Run

```bash
# 1. Export transit routes (standalone, fast)
python -m analysis.export_transit_routes

# 2. Run one scenario first to validate
python -m analysis.run_pipeline --scenario baseline

# 3. Build policy scenarios (Policy A: GTFS, Policy B: OSM)
python -m analysis.scenario_builder

# 4. Run all 4 scenarios (~75 min total)
python -m analysis.run_pipeline

# 5. Push exports
git add data/export/*.json
git commit -m "Add full 4-scenario analysis exports"
git push
```

```bash
# Serve visualization (MacBook or any machine)
python3 -m http.server 8000 --directory visualization/
# Open http://localhost:8000
```

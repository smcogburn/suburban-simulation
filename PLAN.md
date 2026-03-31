# Suburban Simulation — Current State & Plan
*Last updated: 2026-03-30*

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
| `routing.py` | Working — TravelTimeMatrix + DetailedItineraries, generalized cost mode choice. WALK mode added as separate routing pass. car_penalty_min=8 added. Commute/local diagnostics added. |
| `congestion.py` | Working — dynamic 2-pass BPR, 30×5-min time windows |
| `exporter.py` | Working — exports trips/congestion/metadata JSON (WALK trips skipped from viz, stats only) |
| `scenario_builder.py` | Written — builds Policy A (5-min headways) and Policy B (OSM bike lanes) |
| `run_pipeline.py` | Working — skip buildings if exist, 20-origin DetailedItineraries cap. `--diag-only` flag added. |
| `export_transit_routes.py` | Working — exports GTFS shapes for visualization overlay |
| `clip_gtfs.py` | **New** — bbox+time-window filter, run once before pipeline. Cuts 1.5M -> 56k stop_times (96%). |

### ✅ Visualization (Three.js — fully working)

All JS modules written and working:
- `SceneManager.js` — Three.js scene, full corridor scale (camera far=200000)
- `RoadNetwork.js` — roads with live congestion coloring (30 windows, backward interpolation)
- `AgentSystem.js` — trip agents, per-mode x-ray filter, live counts
- `Buildings.js` — building footprints
- `TimeController.js` — play/pause/speed
- `ScenarioPanel.js` — scenario switching
- `CinematicCamera.js` — idle cinematic mode (needs new shot coordinates for Annapolis corridor)
- `TransitLayer.js` — GTFS route overlay (hidden by default; debug toggle via `T` key or button)
- `DataLoader.js` — JSON fetching and caching
- `main.js` — render loop, x-ray click handlers, live mode count display, transit routes debug toggle

### ✅ Data Available

| File | Size | Notes |
|------|------|-------|
| `data/export/buildings.json` | 71 MB | Annapolis/Bowie corridor buildings |
| `data/export/roads.json` | 19 MB | Road network with capacities |
| `data/export/trips_baseline.json` | 11 MB | Baseline trip paths (20 origins × all dests). Baseline confirmed working. |
| `data/export/congestion_baseline.json` | 10 MB | 30-window BPR congestion |
| `data/export/metadata.json` | 1 KB | Mode share stats (baseline: CAR 97.3%, TRANSIT 0.8%, BIKE 1.8%, WALK 0.1%) |
| `data/export/transit_routes.json` | 485 KB | GTFS route shapes for overlay (debug only) |

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
noise_std_min = 15               # individual preference variation (upper range of suburban models)
transit_ivt_factor = 0.85        # productive transit time discount
bike_ivt_factor = 1.15           # cycling effort penalty
car_bpr_factor = 1.0             # free-flow first pass, BPR applied second pass
car_penalty_min = 8              # parking search + egress walk (standard mode choice practice)

# Bike routing
BIKE_MAX_LTS_BASELINE = 3        # LTS 3 = confident cyclist on secondary roads, no arterials
                                 # (arterials are LTS 4 without infrastructure → excluded)
                                 # Policy B tags arterials as LTS 2 → they become accessible
                                 # This is the mechanism that generates Policy B's bike mode shift

# Walk routing
WALK_MAX_MINUTES = 45            # r5py walk trips capped at 45 min (~3.75 km)

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
| Near-0% transit/bike — car had no access/egress penalty | Added car_penalty_min=8 min (parking + walk from lot) |
| WALK never appeared as mode option | Added separate WALK TravelTimeMatrix pass, capped at 45 min |
| No visibility into why transit/bike low | Added routing coverage diagnostics + commute/local trip breakdown |
| Runtime 18 min → 188 min after adding PG County GTFS | Identified: 84k stop times. Fix (GTFS bbox clip) not yet done. |
| Transit route overlay shown in x-ray mode (paths inaccurate) | Hidden by default; debug toggle via T key or corner button |
| 188-min pipeline runtime (was 18 min) | GTFS clipped: 1.5M -> 56k stop_times via clip_gtfs.py |
| Metro GTFS loaded but serves 0 trips in study area | Removed from GTFS_FEEDS in config.py |

---

## What Still Needs to Be Done

### Immediate (before symposium)

- [x] **Re-run baseline** — completed overnight. Results: CAR 97.3%, TRANSIT 0.8%, BIKE 1.8%, WALK 0.1%
- [x] **Fix GTFS runtime** — `clip_gtfs.py` written and run. Combined bbox+time-window filter cuts 1.5M total stop_times to 56k (96% reduction). MTA local bus was real culprit (1.375M -> 15k). Metro removed from config (0 trips in study area). Expected runtime: ~20-30 min/scenario.
- [ ] **Run scenario_builder.py** — builds Policy A GTFS (5-min headways) + Policy B OSM (bike lanes)
- [ ] **Run remaining 3 scenarios** — policy_a, policy_b, policy_ab
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

# Results & Conclusions
*Suburban Simulation — Annapolis/Bowie/Crofton Corridor, MD*
*STEM Senior Thesis: "Designing Better Suburbs: Simulating the Impact of Urban Planning Strategies on Quality of Life"*

---

## The Core Question

Can targeted infrastructure investments meaningfully shift how people travel in a car-dependent American suburb? This project simulates two policy interventions across the Annapolis–Bowie–Crofton corridor of Maryland and measures their effect on transportation mode share during the morning rush hour (7:00–9:30 AM).

---

## The Study Area

The Annapolis/Bowie/Crofton corridor is a prototypical American suburb: low-density residential development, arterial roads connecting strip malls and office parks, minimal pedestrian infrastructure, and transit that exists but is rarely competitive with driving. It spans Anne Arundel and Prince George's counties, covering Bowie, Crofton, Odenton, Annapolis, and Edgewater.

The simulation models 200 residential origins (weighted by building footprint area) paired with 159 destinations — 9 regional employment centers routed to by all origins (commute trips) and 150 local POIs (grocery, school, pharmacy, restaurant) paired only with origins within 5km (local trips). Total: 31,800 OD pairs per scenario.

---

## The Two Policies

| Policy | What It Models |
|--------|---------------|
| **Baseline** | Existing network: current bus headways, no protected bike infrastructure |
| **Policy A** | 5-minute bus headways on all local bus routes (AAC, PG County TheBus, MTA local) |
| **Policy B** | Protected bike lanes on all primary, secondary, and tertiary arterials |
| **Both** | Policies A and B combined |

---

## Results

| Scenario | Car | Transit | Bike | Walk |
|----------|-----|---------|------|------|
| Baseline | 97.3% | 0.8% | 1.8% | 0.1% |
| Policy A (5-min bus) | 97.5% | 0.8% | 1.6% | 0.1% |
| Policy B (bike lanes) | 95.8% | 0.7% | 3.4% | 0.1% |
| Both policies | 95.9% | 0.6% | 3.5% | 0.1% |

*Based on 31,800 synthetic OD pairs. Each simulated trip represents approximately 500 real trips. Mode choice uses a generalized cost model with individual preference noise (σ=15 min) calibrated to suburban discrete choice literature.*

---

## Conclusions

### 1. Protected bike lanes work. Frequent buses don't — not here.

Policy B (bike lanes) roughly **doubles cycling mode share** from 1.8% to 3.4% — the single most significant shift in the simulation. Policy A (5-minute bus headways) moves the needle by essentially nothing: transit stays at 0.8% with or without it.

This is a counterintuitive result. Frequency is commonly cited as the most important lever in transit improvement. Why doesn't it work here?

### 2. The barrier to transit isn't waiting. It's total travel time.

The routing diagnostics reveal the problem clearly. For local trips (within 5km), the median transit trip takes **53 minutes longer than driving**. Breaking that down:

- Walk to bus stop: ~7 min
- Wait (30-60 min headways → ~20 min average wait): ~20 min
- Bus ride + transfers: ~20 min
- Walk from stop to destination: ~5 min
- **Total: ~52 min**

vs. driving the same trip in ~10 minutes.

Policy A cuts the wait from ~20 min to ~2.5 min — saving ~17 minutes. But a 36-minute gap still remains. At the preference noise level calibrated for suburban populations (σ=15 min), very few travelers will switch modes for a 17-minute improvement when the alternative is still 36 minutes slower.

The fundamental barrier is not headway. It is route structure, land use density, and the absence of dedicated bus lanes that would make the in-vehicle portion competitive. Frequency improvements in low-density suburbs run into diminishing returns because wait time is only one component of a much larger penalty.

### 3. Bike lanes work because they address travel time directly.

Policy B raises the maximum bicycle traffic stress level from LTS 3 to LTS 4 for cycling, meaning cyclists can use arterial roads that were previously too hostile to ride on. In the baseline, cyclists are routed around arterials via circuitous residential streets — a 5km trip by crow-fly becomes an 8-10km trip by safe route. The median bike-vs-car gap for local trips was **25 minutes** in baseline.

With protected lanes on arterials, cyclists can take direct routes. The gap drops substantially, and with individual preference heterogeneity, a meaningful share of local short trips (grocery runs, school trips, pharmacy) shift to cycling.

The combined policy (Both) adds almost nothing beyond Policy B alone — the bike gain is nearly identical, and transit still doesn't move. This reinforces that the two policies address different barriers and bike infrastructure is doing the heavy lifting.

### 4. The commute trips are irreversibly car-dependent.

Commute trips (200 origins × 9 regional employment centers) are long-distance by design — averaging 15-25km. Transit coverage for these pairs is only 20% (most origins have no transit route to employment centers at all). Bike coverage is 32% but the median trip is far too long to cycle. These trips are structurally car-dependent regardless of policy.

The interventions only have traction on **local trips** (within 5km). This has implications for how suburban policy should be targeted: frequency investments affect the wrong trip types for the modal penalties that actually exist.

### 5. Absolute mode share numbers reflect reality, not model failure.

97% car share in a suburb like Bowie/Crofton is not a model artifact — it is roughly consistent with American Community Survey commute data for these areas (typically 90-95% drive-alone). The model's 97.3% baseline is plausible. Policy B reaching 3.4% cycling would still be below Amsterdam (38%) or even Washington DC (5%), but it would represent a meaningful improvement for a car-dominated American suburb and is comparable to the best-performing US suburban cycling corridors.

---

## Methodological Notes

### What the model does well
- **Realistic OD generation**: proximity-weighted sampling ensures local trips are actually local and commute trips are actually long-distance
- **Generalized cost mode choice**: individual preference noise (σ=15 min) captures heterogeneity — not everyone makes the purely "rational" choice
- **Car access/egress penalty**: car travel times include 8 min for parking + walk to destination, making the comparison fairer
- **BPR congestion**: road travel times adjust for volume-delay effects across 30 five-minute time windows

### Known limitations
- **Transit routing coverage**: only 18% of OD pairs have a valid transit route. This partly reflects real network gaps (many residential areas have no nearby stops) but may also undercount coverage on the margins.
- **Synthetic trip generation**: 200 origins from a study area of ~200,000 residents is a small sample. Results are directionally correct but exact percentages should be treated as illustrative.
- **Policy B mechanism**: R5 (the routing engine) does not reliably use `cycleway=track` OSM tags to lower LTS scores on parent road ways. The protected lane effect is modeled via a per-scenario LTS cap rather than the OSM tag directly. This is methodologically transparent but means the model can't distinguish between "protected lane on this specific road" and "all arterials improved."
- **No induced demand**: the model holds total trips fixed. In reality, better cycling infrastructure generates new trips and new cyclists. Mode shift is likely understated for Policy B.
- **Walk mode**: only 2% of OD pairs are walkable within the 45-min cap — consistent with suburban distances but means walk results are statistically thin.

---

## The Long Road to These Numbers

Getting to a working simulation involved solving problems across every layer of the stack. A non-exhaustive list:

### Data and infrastructure problems
- **GTFS feeds had expired/future calendars**: AAC buses ended service in 2023 (per the feed); PG County hadn't started yet (starts Dec 2025). Both required manual date fixes before any transit routing was possible.
- **Metro GTFS loaded but covered zero trips**: The DC Metro Green/Orange line feed was included on the assumption it reached the study area — it doesn't. 5,138 stop_times loaded and contributed nothing except computation time.
- **1.5 million stop_times killing runtime**: MTA Maryland local bus is a statewide feed. Loading it unclipped ballooned network build time from 18 minutes to 188 minutes. A bbox + time-window clipper (`clip_gtfs.py`) reduced the total across all feeds from 1,501,265 to 56,620 stop_times (96% reduction).
- **Study area moved mid-project**: The original simulation targeted Columbia/Ellicott City. The study area was relocated to the Annapolis/Bowie/Crofton corridor, requiring re-clipping the OSM PBF, regenerating all buildings/roads, and updating every coordinate reference in the codebase.

### Mode choice model problems
- **Near-zero transit and bike share**: The original model picked the fastest mode with no noise — 100% car. Adding generalized cost with individual preference noise (σ=12-15 min) was necessary to capture the heterogeneity of real travel behavior.
- **Car had no access/egress cost**: r5py returns pure in-vehicle time for car. Transit times include walking to stops and waiting. Without an 8-minute car penalty for parking/egress, the comparison was structurally rigged against transit.
- **Walk mode missing entirely**: WALK was never computed as a separate mode — only included as part of TRANSIT+WALK routing. A separate TravelTimeMatrix pass (capped at 45 min) was needed to surface walk as an option.
- **Policy B had zero effect**: The initial implementation tagged OSM ways with `lts=2` and `cycleway=lane`. R5 ignores the raw `lts` key and `cycleway=lane` (painted marking) is too weak to reliably push high-speed arterials into the LTS 2 range. Fixed by using `cycleway=track` (physical separation) and modeling the infrastructure effect via a per-scenario LTS cap.
- **Policy A only doubled one feed**: The scenario builder was only modifying `mdotmta_gtfs_localbus.zip` while copying AAC and PG County unchanged. Fixed to double all three local bus feeds.

### Visualization and performance problems
- **DetailedItineraries memory bomb**: Passing 200 origins × 30 destinations × 3 modes to r5py crashed a 16GB machine by filling all RAM and triggering 40GB of swap. Fixed by capping to 20 sampled origins for the detailed pass.
- **JVM heap uncapped**: Without `-Xmx10g`, Java claims all available RAM during DetailedItineraries. Set explicitly before r5py initializes.
- **Road flickering**: Three separate causes diagnosed and fixed — `depthWrite: false`, congestion colors updating every render frame (throttled to ≥15 sim-seconds), and road z-fighting with the ground plane (fixed with elevated Y coordinates by road type).
- **Congestion colors anticipating future traffic**: The JS interpolation was lerping forward (current → next window), meaning roads glowed red before the rush arrived. Fixed to lerp backward (previous → current window).
- **metadata.json overwritten per run**: Running `--scenario policy_a` rebuilt the metadata file from scratch, erasing baseline stats. Fixed to merge new stats into existing file on each run.

---

## What This Project Is

This is a STEM senior thesis simulation, not a professional transport demand model. It makes simplifying assumptions, uses synthetic trip generation, and models policy effects in ways that are directionally correct but not calibrated to observed mode share data. The findings should be read as: *"given these modeling choices, this is what the data suggests."*

That said, the core finding — that bike infrastructure outperforms frequency improvements in this type of suburban environment — is consistent with the transport literature on low-density car-dependent suburbs, and the mechanistic explanation (travel time gap vs. wait time gap) is grounded in standard discrete choice theory.

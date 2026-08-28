# Adaptive Search — Design Document

**Status:** design only. No code written yet. This document exists so the
experiment is specified *before* it is run, and so a reader with no background
in search planning can follow it.

**Written:** 28 August 2026
**Owner:** Dewang
**Location:** `simulation/`

---

## 1. The question this answers

> **Does searching high-probability areas first find survivors faster than a
> fixed grid pattern — and does it still win when the probability map is wrong?**

That is the whole experiment. One question, measured against a baseline.

The answer takes the form of a table like this (numbers here are illustrative,
not results):

| Planner | Time to find 50% | 80% | 100% |
|---|---|---|---|
| Lawnmower (baseline) | — | — | — |
| Adaptive | — | — | — |

---

## 2. What is NOT being tested

Stating this first, because the most common way a simulation misleads is by
being read as testing more than it does.

| Not tested | Why |
|---|---|
| The detector | Its recall is an **input** here, already measured at 0.824 |
| The hazard classifier | Not built yet. Its output is one possible source of the prior |
| Real flight | There is no aircraft. No wind, no battery chemistry, no GPS drift |
| Real terrain | Flat grid. No obstacles, no altitude changes, no no-fly zones |
| Real survivors | Positions are placed by us, not observed |

**This tests one thing: the planning strategy.** Everything else is held fixed
or supplied as a parameter.

---

## 3. Glossary

For a reader who has not seen search-planning work before.

| Term | Meaning |
|---|---|
| **Cell / block** | One square of the search area. 20×20 grid, 25 m cells |
| **Truth** | Where the survivors actually are. The simulator knows this; the planner never does |
| **Prior** | What the drone believes *before* flying. A number 0–1 per cell |
| **Posterior** | What it believes *after* evidence. The prior, updated |
| **Belief** | The current probability map. Starts as the prior, changes as the drone flies |
| **Lawnmower** | The baseline: cell 1 → 2 → 3 → … → 100, in fixed order. Also called boustrophedon or coverage path planning |
| **Adaptive** | Our planner: go where expected payoff per second is highest |
| **Utility** | The score a candidate cell gets. Higher = more worth flying to |
| **Staleness** | How long since a cell was last observed. Grows over time, so ignored cells eventually get visited |
| **Footprint** | The patch of ground the camera sees in one frame — 23.09 m here |
| **Correlation** | −1 to +1. How well the prior matches the truth. 0 = the map tells you nothing |

---

## 4. The world

| Property | Value | Why |
|---|---|---|
| Grid | 20 × 20 = 400 cells | Falls out of the two rows below |
| Cell size | 25 m × 25 m | ≈ the 23.09 m footprint, so **one pass observes one cell** |
| Search area | 500 m × 500 m = 0.25 km² | See the coverage arithmetic below |

### Why not 1 km²

An earlier draft of this document said 1 km². That was wrong, and the error is
worth keeping because it changed the design.

```
battery 1200 s  ×  5 m/s        =  6,000 m of flight path
6,000 m  ×  23.09 m swath       =  138,564 m²  covered, at best
```

| Search area | One battery covers |
|---|---|
| 300 × 300 m | 154 % — trivially complete, prioritisation pointless |
| 400 × 400 m | 87 % |
| **500 × 500 m** | **55 %** ← chosen |
| 1000 × 1000 m | **14 %** ← the original figure, and unusable |

At 55 % the drone can search only about half the area in one sortie, so
**which half it chooses is the whole experiment.** Above ~90 % the planner
barely matters; below ~20 % almost nothing gets searched and the result is
noise.
| Base station | Cell (0,0), a corner | The drone launches and must return here |
| Survivors | 20, in 3 clusters | People gather. Our own clip had all 23 within 11.4 m |
| Time step | 1 second | Simple, and matches the frame-rate arithmetic |

The drone occupies one position, moves at a fixed speed, and observes a
footprint beneath it continuously.

---

## 5. Every variable

**Provenance is the important column.** Measured means we have a number from a
real experiment. Assumed means we chose it and must disclose it. Swept means we
deliberately try several values.

### Imported from `backend/config.py` — do not retype these

| Variable | Value | Provenance | What it is |
|---|---|---|---|
| `ALTITUDE_M` | 20.0 | assumed | Flight altitude |
| `CAMERA_FOV_DEG` | 60.0 | assumed | Nadir camera field of view |
| `DRONE_SPEED_MS` | 5.0 | assumed | Ground speed |
| `DEVICE_FPS` | 4.8 | **measured** | Frames per second on the RB3 Gen 2 |
| `ORIGIN_LAT/LON` | 26.405892, 92.233479 | assumed | Search-area origin — central Assam |

Derived from those: **footprint = 2 × 20 × tan(30°) = 23.09 m.**

### The one measured input that drives the algorithm

| Variable | Value | Provenance |
|---|---|---|
| `P_DETECT` | **0.824** | **measured** — recall at conf 0.18, 960 px, on 86,092 instances |

This is the number that makes the belief update meaningful. Because it is
0.824 and not 1.0, "I looked and saw nothing" does not mean "nobody is there."

### Simulation-only parameters

| Variable | Value | Provenance | Real-world analogue |
|---|---|---|---|
| `GRID_N` | 20 | chosen | 20×20 cells of 25 m over a 500 m square |
| `N_SURVIVORS` | 20 | chosen | Unknown in reality — that is the point of searching |
| `CLUSTER_SIGMA` | 0.8 cells | chosen | How tightly people gather |
| `w` | **0.0 / 0.6 / 1.0** | **swept** | How wrong your map happens to be. Uncontrollable in the field |
| `BATTERY_S` | 1200 (20 min) | assumed | Endurance of a multirotor carrying a compute board and camera |
| `RESERVE_FRAC` | 0.15 | assumed | Safety margin before forced return |
| `COMMIT_STEPS` | 20 | chosen | Anti-dithering, see §8 |
| `STALENESS_RATE` | 0.001 /s | chosen | How fast an ignored cell regains attractiveness |
| `SEED` | 0–29 | chosen | 30 repeats, so results are not one lucky layout |

---

## 6. The sensor model

Each second the drone observes the cells under its footprint.

```
for each survivor in an observed cell:
    detected with probability P_DETECT = 0.824
```

A survivor already found stays found. A survivor missed can be found on a
later pass — which is exactly why revisiting is worth modelling.

**Simplification, disclosed:** real detection probability falls with altitude
and rises with the number of looks. We use one flat number, the measured
recall at our shipped settings. Sweeping altitude is future work.

---

## 7. The belief update

The core mechanic. Written out because it is the part a reader most needs.

Each cell holds `b` = probability that at least one **undiscovered** survivor
is there. It starts at the prior.

**Observed a cell, found nothing:**

```
b  ←   b(1 − p)  /  [ b(1 − p) + (1 − b) ]        where p = 0.824
```

Worked example — a cell that started at `b = 0.50`:

| Passes | b after |
|---|---|
| 0 | 0.500 |
| 1 | 0.150 |
| 2 | 0.030 |
| 3 | 0.005 |

Belief collapses fast but never reaches zero. **One pass is not proof of
absence** — and that is a direct consequence of a measured number, not a
modelling choice.

**Found someone:** that cell's neighbours are boosted, because survivors
cluster:

```
b[neighbour] ← min(1, b[neighbour] × 1.5)
```

This one rule produces the "search nearby after arriving" behaviour without
any special-case code for it.

---

## 8. The two planners

### Baseline — Lawnmower

Visit cells in fixed boustrophedon order: row 0 left-to-right, row 1
right-to-left, and so on. Ignores the prior entirely. Returns to base when
battery requires.

This is the standard against which the result is measured. It is what most
UAV search actually does today.

### Ours — Adaptive

Every `COMMIT_STEPS` seconds, or immediately on a detection, score every cell:

```
utility(cell) =  ( b[cell] + staleness[cell] )  /  ( travel_time(here → cell) + search_time )
```

Fly to the highest. Three properties come out of that one line:

1. **Expected finds per second**, not per cell — so a slightly-worse cell that
   is much closer wins. This is the "search nearby first" behaviour.
2. **Staleness grows with time-since-observed**, so an ignored cell eventually
   outranks a mildly interesting one. This *enforces* full coverage rather
   than hoping for it.
3. **Cells crossed en route are observed and updated**, because the camera is
   on the whole way. Travel is not dead time.

**Anti-dithering.** Without a commitment period the drone flips between two
similar cells and searches nothing. Same problem, and same fix, as
`BAND_HYSTERESIS = 0.03` in the priority scorer: commit for `COMMIT_STEPS`
unless something clearly better appears.

**Battery-aware return.** Turn back when

```
remaining_battery  ≤  travel_time(here → base) × (1 + RESERVE_FRAC)
```

The threshold is a *function of position*, not a fixed number — far from base
you must turn back earlier. The return path is chosen to cross the highest-value
unobserved cells, so the return leg still searches.

---

## 9. Metrics

| Metric | Why |
|---|---|
| **Time to find 50% / 80% / 100%** | In rescue, early finds matter more than late ones. A single total-time figure hides a front-loaded advantage |
| Survivors found within battery | Not every run finds everyone |
| Cells observed at least once | Checks the coverage promise is kept |
| Path length | Sanity check on efficiency |

Every run is repeated over **30 random seeds** and reported as median with
range. A single run proves nothing.

---

## 10. Experiment matrix

| Run | Prior | Target correlation | Question |
|---|---|---|---|
| **A** | Good | ≈ 0.65 | Best case — how good can this get? |
| **B** | Mediocre | ≈ 0.35 | Realistic messy information |
| **C** | **Uniform** | **0.00** | **No information at all — the hard test** |

Each run: both planners, 30 seeds, same survivor layouts. Only the planner and
the prior change.

**Run C is the one that matters.** With a uniform prior the drone starts out
behaving like a lawnmower — nothing is more attractive than anything else. If
adaptive still wins, the advantage comes from **learning during flight**, not
from starting lucky. That claim survives a reviewer saying "your map is
probably wrong."

`w` is tuned until the correlation lands near the target. **We report the
correlation, never `w`** — `w` means nothing outside this code.

---

## 11. Assumptions, stated plainly

Anything here is a limitation, not a hidden flaw.

1. Flat terrain, no obstacles, no no-fly zones
2. Detection probability constant with altitude and viewing angle
3. Survivors do not move
4. Perfect localisation — no GPS error
5. Battery drains linearly with time; no wind, no payload variation
6. The drone knows its own position exactly
7. One aircraft. No multi-drone coordination
8. Cells are observed atomically — no partial coverage

Items 3 and 5 are the ones most likely to matter in reality.

---

## 12. How each input would be obtained in a real deployment

The simulation invents these. A real mission would source them. Using the
Assam floods as the worked example, since our origin coordinate
(26.405892, 92.233479) sits in the Brahmaputra flood plain.

| Simulation input | Real source |
|---|---|
| `truth` | **Never known.** This is what the search is for |
| `prior` | Built from the layers below |
| ↳ terrain | Copernicus / SRTM elevation — finds dry ground |
| ↳ water extent | Sentinel-1 **radar** — sees through monsoon cloud, unlike optical |
| ↳ shelter points | OpenStreetMap embankments, raised roads, schools |
| ↳ relief camps | ASDMA publishes camp locations during flood events |
| ↳ population | WorldPop or Census |
| ↳ live hazards | Our own hazard classifier, from a Phase 1 survey pass |
| `P_DETECT` | Already measured — 0.824 |
| `w` | **Unknowable before the flight.** Estimable afterwards, once people are found |

### The flood-specific signal

> **In a flood, survivors are on high ground surrounded by water.**

```
high prior = dry ground  AND  surrounded by flood  AND  near settlement
low prior  = deep water,  OR  dry land far from any flooding
```

Elevation minus flood extent gives the dry islands directly. This is more
informative than generic building density, and it is specific to the disaster
type — which is the kind of domain knowledge that separates a working system
from a generic planner.

### The formula for building a real prior

The simulation invents the prior. A real mission computes it. This is how.

**Use the same pattern as `backend/priority.py`** — a weighted average of
normalised 0–1 terms, with the rule that any term which cannot rank anything is
dropped and the remaining weights renormalised. That rule already exists in this
codebase for survivor scoring; the prior builder is the same idea applied to
cells instead of people.

```
prior(cell) = normalise(  w_s · shelter(cell)
                        + w_b · structure(cell)
                        + w_p · population(cell)
                        + w_h · hazard(cell)      )
```

| Term | What it measures | Source | Available |
|---|---|---|---|
| `shelter` | Dry ground surrounded by water | DEM − flood extent | Before flight |
| `structure` | Buildings, roads, embankments per cell | OpenStreetMap | Before flight |
| `population` | People normally living here | WorldPop / Census | Before flight |
| `hazard` | Fire, flood, collapse detections | Our classifier, Phase 1 survey | After the survey pass |

Only `hazard` needs the aircraft. The other three are computed on the ground
before takeoff, which is what makes a Phase 2 adaptive search possible at all.

### The flood-specific term, worked out

For the Brahmaputra floods the strongest single signal is not building density:

> **In a flood, survivors are on high ground surrounded by water.**

```
wet(cell)      = flood extent from Sentinel-1 radar        (sees through cloud)
dry(cell)      = NOT wet
isolated(cell) = dry(cell) AND most neighbours are wet     (a dry island)
shelter(cell)  = isolated(cell) × structure(cell)
```

A dry island with an embankment or a school on it is where people go. A dry
cell far from any flooding is where people already are and are safe — low
prior, not high.

### The hazard term does not have one sign

A mistake worth avoiding: hazard proximity does not always mean "people here".

| Hazard | Effect on prior | Why |
|---|---|---|
| Collapsed structure | **Raise** | People are trapped inside it |
| Flood edge | **Raise** | People are stranded at the waterline |
| Active fire | **Lower** nearby, raise at the perimeter | Occupants have fled outward, if they could |

Treating all hazards as attractors would send the aircraft into the one place
people have already left.

### How to find out which correlation band a method achieves

You cannot measure this before or during a mission. You can measure it
**afterwards**, and that is how the method gets calibrated:

1. Take a historical event — an Assam flood with published relief-camp and
   rescue records
2. Build the prior **using only data that existed before that event**
3. Compare it against where people were actually found
4. Compute the correlation

Repeat over several events and you learn the distribution your method produces.
That number, not a chosen `w`, is what belongs in a paper. It is also the single
most valuable follow-up experiment available here.

### Resolving the chicken-and-egg

To see that a building collapsed you must fly over it — so the hazard
classifier cannot seed the prior for its own flight. Two-phase flight resolves
this, and matches how real search-and-rescue is run:

| Phase | Altitude | Speed | Purpose |
|---|---|---|---|
| **1 · Survey** | High | Fast | Coarse pass. Spots hazards and structures. **Builds the prior** |
| **2 · Search** | 20 m | 5 m/s | Detailed adaptive search using that prior |

Only Phase 2 is simulated here. Phase 1 is future work.

---

## 13. What we can and cannot claim

**Can:**

> "Under simulation, with a detector at our measured 0.824 recall, adaptive
> search reached 80% of survivors in X minutes against Y for a lawnmower — and
> it still won with no prior information at all."

**Cannot:**

> "Our system finds survivors 40% faster."

That is a flight claim, and there is no aircraft. Every figure must carry the
word **simulation**, matching the scope table in `README.md`, which already
lists adaptive search planning as *research direction — simulation only, not
flown*.

---

## 14. Files

```
simulation/
├── DESIGN.md      this document — read before the code
├── config.py      simulation-only parameters; imports backend/config.py
├── world.py       grid, survivors, priors, sensor model
├── planners.py    lawnmower and adaptive
├── run.py         experiment runner, CLI
└── results/       output plots and a results table
```

**`backend/config.py` is the single source for shared constants.** Footprint,
speed, altitude and recall are imported, never retyped. This project has
already had one number drift across six files; that is not repeated here.

---

## 15. Future work

| Item | Why it was deferred |
|---|---|
| Real OSM / DEM prior for a named area | Needs data plumbing; the synthetic prior tests the planner just as well |
| Phase 1 survey simulated | Doubles the scope |
| Moving survivors | Realistic but adds a dynamics model |
| Multi-drone coordination | A different research problem |
| Altitude-dependent detection | Requires measuring recall at several altitudes |
| Live dashboard integration | Presentation, not research |

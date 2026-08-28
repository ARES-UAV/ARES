# Adaptive Search — Experiment Log

**Run:** 28 August 2026
**Command:** `python simulation/run.py --seeds 100`
**Machine:** MacBook Air, `.venv-qai`
**Design:** `simulation/DESIGN.md` — written before the code, unchanged since
**Raw output:** `simulation/results/results.json`, `results.md`, `found_vs_time.png`

---

## 1. The question

> Does searching high-probability areas first find survivors faster than a fixed
> grid pattern — and does it still win when the probability map is wrong?

---

## 2. Configuration as run

| | Value | Provenance |
|---|---|---|
| **P(detect)** | **0.824** | **MEASURED** — recall at conf 0.18, 960 px, 86,092 instances |
| Altitude / FOV / speed | 20 m / 60° / 5 m/s | imported from `backend/config.py`, assumed |
| Footprint | 23.09 m | derived, `2·H·tan(FOV/2)` |
| Grid | 20 × 20 cells of 25 m | chosen — cell ≈ footprint, so one pass observes one cell |
| Search area | 500 × 500 m = 0.25 km² | chosen — see §3 |
| Battery | 1200 s (20 min) | assumed |
| Return reserve | 15 % | assumed |
| Survivors | 20 in 3 clusters, σ = 0.8 cells | chosen |
| Commit period | 20 s | chosen — anti-dithering |
| Staleness rate | 0.0004 /s | chosen — enforces eventual coverage |
| Neighbour boost | ×1.5 per find | chosen — survivors cluster |
| **Belief cap** | **0.95** | chosen — see §6, bug 1 |
| Seeds | 100 | both planners fly identical worlds |

---

## 3. Why the area is 500 m, not 1 km

The first draft of the design said 1 km². The arithmetic killed it:

```
1200 s × 5 m/s               =   6,000 m of flight path
6,000 m × 23.09 m swath      = 138,564 m² covered, at absolute best
```

| Search area | One battery covers |
|---|---|
| 300 × 300 m | 154 % — trivially complete, prioritisation pointless |
| **500 × 500 m** | **55 %** ← chosen |
| 1000 × 1000 m | 14 % — the original figure, and unusable |

At 55 % the drone searches about half the area, so **which half it picks is the
experiment.**

---

## 4. Results — 100 seeds, medians

| Prior | Corr. | Planner | Found /20 | Coverage | t50 | t80 | Reached 80 % |
|---|---:|---|---:|---:|---:|---:|---:|
| good | 0.65 | lawnmower | 11.0 | 56 % | 935 s | 985 s | 10/100 |
| good | 0.65 | **adaptive** | **20.0** | 33 % | **291 s** | **578 s** | **81/100** |
| mediocre | 0.38 | lawnmower | 10.5 | 56 % | 938 s | 985 s | 10/100 |
| mediocre | 0.38 | **adaptive** | **19.0** | 42 % | **430 s** | **782 s** | **79/100** |
| uniform | −0.01 | lawnmower | 11.0 | 56 % | 938 s | 985 s | 10/100 |
| uniform | −0.01 | **adaptive** | 11.0 | 48 % | **715 s** | **900 s** | **18/100** |

**Speed-up to 50 % of survivors:**

| Prior | Speed-up |
|---|---:|
| good (0.65) | **3.21×** |
| mediocre (0.38) | **2.18×** |
| uniform (−0.01) | **1.31×** |

### The column that says the most

A lawnmower reaches 80 % of survivors in **10 runs out of 100**, whatever the
prior — it cannot use information, so information does not help it. Adaptive
with a decent prior does it in **81 out of 100**.

---

## 5. What the uniform row actually says

This is the row to be careful about.

With a prior correlating **−0.01** with truth — no information whatsoever —
adaptive found **11.0 of 20**, and so did the lawnmower. **Identical.**

What differs is *when*: 715 s to half, against 938 s. A **1.31× speed-up on
time, and no advantage at all on the number found.**

So the honest claim is narrower than "it wins with no information":

> With no prior information, adaptive reaches half the survivors 1.31× faster,
> but finds no more of them overall.

The speed comes from in-flight learning: with a flat prior nothing is more
attractive than anything else, so the drone starts out flying like a lawnmower.
The moment it finds one person, the neighbour boost makes it work that area
instead of marching on.

### 30 seeds was optimistic

| Prior | 30 seeds | 100 seeds |
|---|---:|---:|
| good | 3.13× | 3.21× |
| mediocre | 2.19× | 2.18× |
| **uniform** | **1.54×** | **1.31×** |

The informed cases were stable. The uniform figure fell by 15 %. **Quote the
100-seed numbers.** This is exactly why the design specified repeats rather than
a single run.

---

## 6. Two bugs, and how they were caught

Both were found by looking at a diagnostic rather than the headline. In both
cases the "found" number looked plausible while something was wrong.

### Bug 1 — the absorbing state

**Symptom:** adaptive found 11/20 with a good prior, and covered only **12.6 %**
of the area. The headline looked acceptable; the coverage did not.

**Cause:** the Bayesian miss-update

```
b  ←  b(1−p) / [ b(1−p) + (1−b) ]
```

at `b = 1.0` gives `0.176 / (0.176 + 0) = 1.0`. Belief at exact certainty can
never come down, however many times the drone looks and finds nobody.

The neighbour boost made that reachable: a cluster of seven people fires ×1.5
seven times — 17×, clipped to 1.0 — so the whole neighbourhood locked at maximum
attractiveness. **The drone found a cluster and never left it.**

**Fix:** `BELIEF_CAP = 0.95`. Certainty stays out of reach, so evidence always
moves belief.

**Effect:** 11/20 → **20/20**; coverage 12.6 % → 32 %.

### Bug 2 — the backwards curve

**Symptom:** the plotted line for adaptive went from 20 survivors at 400 s
*down* to 16 at 1040 s.

**Cause:** plotting `median(t50)`, `median(t80)`, `median(t100)` as three points.
Each median is over a **different subset of seeds**, because not every run
reaches 80 % or 100 %. The runs that reach 100 % are the lucky fast ones, so
their median lands earlier than t80's median taken over many more runs.

**Fix:** build the curve from per-seed traces — for each seed count how many were
found by time *t*, then take the median of those counts at every *t*. Monotonic
by construction, and it uses every run.

---

## 7. What may and may not be claimed

**May:**

> In simulation, with a detector at our measured 0.824 recall, adaptive search
> reached half the survivors 3.2× faster than a lawnmower grid and found 20 of
> 20 against 11. With a prior correlating zero with reality it was still 1.3×
> faster to half, though it found no more people overall.

**May not:**

> Our system finds survivors 3× faster.

That is a flight claim, and there is no aircraft. Every figure carries the word
**simulation**, matching the scope table's *"adaptive search planning — research
direction, simulation only, not flown."*

### The cost, stated

Adaptive covers **33 %** of the area against the lawnmower's **56 %**. It finds
more people, sooner, over less ground. If the objective were "map the whole
area" rather than "find people fast", the lawnmower wins. That is a real trade,
and it belongs in the table rather than in a footnote.

---

## 8. Limits of this result

1. Simulation, not flight. No wind, no GPS error, no obstacles, no terrain
2. Detection probability is constant — real recall varies with altitude and angle
3. Survivors do not move
4. The prior is synthetic. Its correlation is a swept parameter, not a
   measurement of any real information source
5. One aircraft, no multi-drone coordination
6. Battery drains linearly with time
7. Results are medians over 100 random layouts of one world type — clustered
   survivors on flat ground

---

## 9. What would strengthen it next

| Item | Why |
|---|---|
| A real prior from OSM + DEM + Sentinel-1 for a named area | Turns the swept `w` into a measured correlation for an actual method |
| Retrospective validation against a historical flood | The only way to learn which correlation band our prior-building actually achieves |
| Phase 1 survey simulated | Closes the chicken-and-egg between hazard detection and the prior |
| Altitude-dependent detection | Needs recall measured at several altitudes |
| Moving survivors | Realistic; adds a dynamics model |

# Adaptive Search — Experiment Log

**Run:** 22 September 2026 (re-run; first run 28 August 2026)
**Command:** `python simulation/run.py --seeds 100`
**Machine:** MacBook Air
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
| good | 0.65 | lawnmower | 11.0 | 55 % | 905 s | 985 s | 10/100 |
| good | 0.65 | **adaptive** | **20.0** | 33 % | **291 s** | **578 s** | **81/100** |
| mediocre | 0.38 | lawnmower | 11.0 | 55 % | 905 s | 985 s | 10/100 |
| mediocre | 0.38 | **adaptive** | **19.0** | 42 % | **430 s** | **782 s** | **79/100** |
| uniform | −0.01 | lawnmower | 11.0 | 55 % | 905 s | 985 s | 10/100 |
| uniform | −0.01 | **adaptive** | 11.0 | 48 % | **715 s** | **900 s** | **18/100** |

**Speed-up to 50 % of survivors:**

| Prior | Speed-up |
|---|---:|
| good (0.65) | **3.11×** |
| mediocre (0.38) | **2.10×** |
| uniform (−0.01) | **1.27×** |

### Why these differ from the 31 August write-up

This table was re-run on 22 September because the numbers recorded here could
not be reproduced from `results/results.json` — the file on disk was a 30-seed
run, and the 100-seed output it was meant to hold had been overwritten. The
re-run reproduces **every adaptive figure exactly** (291 / 578 / 81-of-100,
430 / 782 / 79-of-100, 715 / 900 / 18-of-100). What moved is the lawnmower's
t50: **935 / 938 / 938 s → 905 s**, and with it the speed-ups, 3.21× → 3.11×.

The cause is commit `828877b`, the only commit to touch `simulation/` since.
`P_DETECT` is unchanged at 0.824, so this is not the v8s threshold change that
`V8S_THRESHOLD.md` anticipated.

The new figure is also the more obviously correct one. **The lawnmower ignores
the prior entirely**, so it must fly the same path through the same worlds in
all three rows — and it now reports an identical 905 s in each. The old table
had it at 935 / 938 / 938, three different numbers for a planner that cannot
see the thing being varied. That was the bug, and the re-run removed it.

### The caveat that belongs beside every speed-up

**The lawnmower's t50 is a median over the 58 seeds of 100 in which it reached
half the survivors at all.** In the other 42 it never got there, and those runs
are excluded rather than counted as failures. That discards the baseline's
*worst* outcomes, so **3.11× understates the advantage.** The adaptive planner
with a good prior reaches half in 100 of 100.

Quote the ratio with the denominator, or quote 58/100 vs 100/100 instead. Do
not quote the ratio as though both planners finished the task.

### The column that says the most

A lawnmower reaches 80 % of survivors in **10 runs out of 100**, whatever the
prior — it cannot use information, so information does not help it. Adaptive
with a decent prior does it in **81 out of 100**.

---

## 5. What the uniform row actually says

This is the row to be careful about.

With a prior correlating **−0.01** with truth — no information whatsoever —
adaptive found **11.0 of 20**, and so did the lawnmower. **Identical.**

What differs is *when*: 715 s to half, against 905 s. A **1.27× speed-up on
time, and no advantage at all on the number found.**

So the honest claim is narrower than "it wins with no information":

> With no prior information, adaptive reaches half the survivors 1.27× faster,
> but finds no more of them overall.

The speed comes from in-flight learning: with a flat prior nothing is more
attractive than anything else, so the drone starts out flying like a lawnmower.
The moment it finds one person, the neighbour boost makes it work that area
instead of marching on.

### 30 seeds was optimistic

| Prior | 30 seeds | 100 seeds |
|---|---:|---:|
| good | 3.13× | 3.11× |
| mediocre | 2.19× | 2.10× |
| **uniform** | **1.54×** | **1.27×** |

The informed cases were stable. The uniform figure fell by 18 %. **Quote the
100-seed numbers.** This is exactly why the design specified repeats rather than
a single run — and §4's re-run note is the second time that has paid off.

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

## 6b. "Do you ever find the rest?" — the multi-sortie campaign

`tools`: `simulation/multi_sortie.py` · record `simulation/results/multi_sortie.json`

The strongest objection to § 7's trade — adaptive covers 33 % against the
lawnmower's 55 % — is the obvious one:

> *"A grid is systematic. Fly it long enough and it finds everyone. Yours goes
> where it guesses. Do the ones it skipped ever get searched?"*

One 20-minute sortie cannot answer that: neither aircraft finishes the area.
So fly four, back to back, over one persistent world. The lawnmower resumes its
pattern where the battery stopped it — what an operator actually does. Adaptive
keeps its belief map, so cells it skipped have been accruing **staleness** the
whole time.

**Cumulative found (coverage), 60 seeds, medians:**

| prior | planner | sortie 1 | sortie 2 | sortie 3 | sortie 4 |
|---|---|---|---|---|---|
| good | lawnmower | 10.0 (55 %) | **17.0 (100 %)** | 17.0 (100 %) | 17.0 (100 %) |
| good | **adaptive** | **20.0** (33 %) | 20.0 (77 %) | 20.0 (99 %) | 20.0 (100 %) |
| mediocre | lawnmower | 10.0 (55 %) | 17.0 (100 %) | 17.0 (100 %) | 17.0 (100 %) |
| mediocre | **adaptive** | 19.0 (42 %) | **20.0** (82 %) | 20.0 (99 %) | 20.0 (100 %) |
| uniform | lawnmower | 10.0 (55 %) | 17.0 (100 %) | 17.0 (100 %) | 17.0 (100 %) |
| uniform | **adaptive** | 11.0 (48 %) | 18.0 (85 %) | 19.0 (98 %) | **20.0 (100 %)** |

### The objection's premise is wrong

**The lawnmower covers 100 % of the area by sortie 2 — and still finds 17 of
20. Then it stops improving, for ever.**

That plateau is not a coverage failure. It is arithmetic:

```
20 survivors  x  P(detect) 0.824  =  16.5 expected on a single look
                                     measured plateau: 17.0
```

A complete sweep is not a complete search. At our measured recall roughly one
person in six is missed on any given pass, and a planner that visits every cell
exactly once has no mechanism to go back — nothing in a fixed pattern says
"look again".

**Adaptive reaches 20 of 20 from every prior**, including the uninformative
one, because the Bayesian miss-update never drives a cell's belief to zero. One
look is not proof of absence, so a cell that came up empty stays worth
revisiting, and the staleness term guarantees the unvisited ones rise anyway.

### Two claims this supports, and one it retires

**Supports:**

> Adaptive reaches full coverage — 100 % by the third or fourth sortie — so
> skipped cells are queued, not abandoned. The staleness term is a coverage
> guarantee, and it is now measured rather than asserted.

> Over a campaign, adaptive finds **more people**, not merely the same people
> sooner: 20 of 20 against the grid's 17 of 20, with both at 100 % coverage.

**Retires:** the framing in § 7 that the single-sortie coverage gap (33 % vs
55 %) is a straight cost. Across a campaign it is a scheduling difference, and
the grid's higher first-sortie coverage buys it nothing it keeps.

### Caveats

1. Four sorties over one static world. Survivors do not move, and no new ones
   appear — a real second sortie hours later faces a changed scene.
2. Battery swaps are free and instant here. No transit to a landing site, no
   turnaround.
3. The lawnmower could revisit if someone told it to. Nothing in a grid pattern
   does, which is the point — but a fairer "grid plus a second sweep" baseline
   would close part of the 17-vs-20 gap and is worth measuring before the
   claim is used against a sophisticated audience.

### A harness bug worth recording

The first version of this experiment reported the lawnmower **frozen at 55 %
coverage and 11 survivors for every sortie after the first** — a far more
flattering result, and false.

`fly_to` refuses a step that would strand the aircraft and returns without
moving. The sortie loop advanced its pattern index regardless, so across sortie
1 the index walked all 400 cells while the drone sat still, and every later
sortie found the pattern already exhausted. Fixed by advancing the index only
when the aircraft actually reached the cell.

The tell was the coverage column: identical to three decimal places across four
sorties. A real planner does not produce numbers that clean.

---

## 7. What may and may not be claimed

**May:**

> In simulation, with a detector at our measured 0.824 recall, adaptive search
> reached half the survivors 3.1× faster than a lawnmower grid and found 20 of
> 20 against 11. With a prior correlating zero with reality it was still 1.3×
> faster to half, though it found no more people overall.

**May not:**

> Our system finds survivors 3× faster.

That is a flight claim, and there is no aircraft. Every figure carries the word
**simulation**, matching the scope table's *"adaptive search planning — research
direction, simulation only, not flown."*

### The cost, stated

Adaptive covers **33 %** of the area against the lawnmower's **55 %**. It finds
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

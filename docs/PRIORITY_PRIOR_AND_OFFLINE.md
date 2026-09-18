# Three questions answered: the priority score, the prior, and the radio

Written from the code, not from memory. Every constant quoted lives in
`backend/config.py` or `simulation/config.py`.

---

## 1 · How the priority score works

### The formula

A weighted average of three normalised 0–1 terms, and nothing cleverer —
deliberately, because a judge will ask how the ranking works and the answer has
to fit in one sentence.

```
priority  =  0.4 · confidence  +  0.3 · cluster  +  0.3 · hazard
```

| Term | What it measures | Constants |
|---|---|---|
| **confidence** | the detector's confidence on that track's latest detection | — |
| **cluster** | how many other survivors are within 15 m, linear then flat | `CLUSTER_RADIUS_M 15`, `CLUSTER_SATURATION 4` |
| **hazard** | how close the nearest known hazard is | `HAZARD_INFLUENCE_M 50` |

Saturation at 4 neighbours exists so one large group cannot compress everyone
else's cluster term towards zero.

### The rule that actually matters: a term that cannot rank is dropped, not zeroed

**Weights are relative and divided by their own sum.** So when a term says
nothing, it is removed and the rest renormalise:

```
all three          (0.4·C + 0.3·L + 0.3·H) / 1.0
hazard dropped     (0.4·C + 0.3·L) / 0.7   =  0.571·C + 0.429·L
both dropped        0.4·C / 0.4            =  C
```

Two terms can fail to say anything:

- **Hazard** — `config.HAZARDS` is empty until the classifier produces real
  positions. Scoring it `0.0` would read as *"checked, nothing nearby"* and
  pull every survivor down by the hazard weight, making the whole scene look
  calmer than anything measured. Dropping it means **"not measured"**, which is
  the truth.
- **Cluster** — dropped when it comes out *identical for every survivor*. One
  group with everyone inside it cannot order that group.

**On the demo clip both drop, so priority equals confidence exactly** and the
breakdown reads `{"confidence": 0.802}`.

This is not a technicality. Measured on the real clip: keeping a uniform
cluster term adds a flat **+0.4286** to everyone and the scene reads **16 high,
7 critical, nothing below**. Dropping it gives **1 critical, 9 high, 10 medium,
3 low** — a usable ranking instead of a wall of red.

### Bands, and why they have hysteresis

Thresholds **0.25 / 0.50 / 0.75**, plus `BAND_HYSTERESIS 0.03`. Critical needs
0.78 to enter and must fall below 0.72 to leave.

A band is a *state that gets re-read every frame*, not a one-off verdict. Logs
showed single tracks changing band **five times in nine seconds** without the
deadband. Visible consequence: sorted by score, bands can look inverted —
0.274 sitting in *low* above 0.264 in *medium*. That is correct behaviour, and
it is why `band_for` must stay idempotent.

### Two different geometries, on purpose

| Question | Projection | Why |
|---|---|---|
| Where is this survivor? | `bbox_to_latlon` — origin advances along the flight track | map pins, hazard distance |
| How far apart are two survivors? | `bbox_to_reference_latlon` — track held still | the cluster term |

At 5 m/s a three-second gap between two sightings **manufactures fifteen metres
of separation** between people who may have been standing together. Measured
cost of getting this wrong: track 1409, the highest-confidence survivor in the
clip, ranked **21st of 23** under the moving origin and **1st** in the
reference frame.

### Why it is explainable by construction

`score_breakdown` carries each term's renormalised contribution and **sums to
the priority within 1e-3**. The dashboard can answer *"why is this person above
that one?"* from the record alone — no model interpretation required.

---

## 2 · The prior, and what to call it

### The name

**Two maps exist, and keeping them apart is what makes the experiment valid.**

| | |
|---|---|
| `truth` | where survivors actually are. The simulator knows it. **The planner never sees it.** |
| `belief` | what the drone thinks. **The only map the planner may read.** |

The map fed to the planner is the **belief map** (or belief grid). At t = 0 it
*is* the **prior**. Every observation after that updates it, so from the first
second onwards it is a **posterior**. Say *"prior"* for what it launches with
and *"belief map"* for what it flies on — those are the right words and they
are the words in the code.

### How the prior is built

```
prior = (1 − w) · blurred(truth)  +  w · blurred(noise)        clipped to [0.02, 0.95]
```

**Blurred, because a prior is never sharp.** Knowing *"this building holds
people"* makes the neighbouring cells likely too — nobody knows the exact 25 m
square. Blurring also caps how good any prior can be at about **0.65
correlation**, never 1.0. That ceiling is honest, not a bug.

**`w` is a swept dial and is never reported.** What gets published is
`correlation(prior, truth)`, because it is standard and checkable:

| run | w | measured correlation |
|---|---:|---:|
| good | 0.0 | **0.65** |
| mediocre | 0.6 | **0.38** |
| uniform | 1.0 | **−0.01** |

**What "noise" means in the field** — not static. It is your information being
wrong or stale: a building that collapsed last month, a relief camp pitched
yesterday in what the map calls an empty field, an area flagged as burning that
was evacuated hours ago.

### Where a real prior would come from

**State this clearly, because it is the honest gap.** Today the prior is
synthetic and its quality is a swept parameter, not a measurement of any real
information source. In deployment it would be assembled from:

- **OpenStreetMap** — building density, shelters, schools, hospitals
- **A DEM** — high ground, which is where people go in a flood
- **Sentinel-1 SAR** — flood extent, which works through cloud
- **Emergency call locations** and last-known positions
- **A Phase-1 survey pass** by the drone itself, feeding the second sortie

**This is exactly why the uniform-prior case was tested.** If the prior turns
out to be useless, the planner matches a grid and never does worse — measured,
11 against 11.

### What one look does to the belief

**Saw nobody** — Bayes, with the measured miss rate:

```
b ← b(1−p) / [ b(1−p) + (1−b) ]        p = P_DETECT = 0.824
0.50 → 0.15 → 0.03 → 0.005
```

Collapses fast, **never reaches zero**. One pass is not proof of absence, and
that falls straight out of a measured number rather than a modelling
preference.

**Found somebody** — the eight surrounding cells are multiplied by
`NEIGHBOUR_BOOST 1.5`. *This one rule is what makes the drone linger in a
productive area.* There is no "search nearby" special case anywhere in the
code.

**`BELIEF_CAP 0.95` exists because of a real bug.** At b = 1.0 the miss-update
can never bring a cell down — 1.0 × anything ÷ 1.0 stays 1.0. Seven neighbour
boosts reach 17×, clip to 1.0, and the drone finds a cluster and never leaves
it. Capping at 0.95 moved the result from **11/20 to 20/20** and coverage from
**12.6% to 32%**.

### How the planner chooses

```
utility  =  (belief + staleness) / (travel_time + search_time)
```

Three behaviours fall out of that one line:

1. **Expected finds per second, not per cell.** Dividing by travel time lets a
   slightly-worse nearby cell beat a better distant one — the sweep-around-a-
   find behaviour, as arithmetic rather than a special case.
2. **Coverage is guaranteed, not hoped for.** `staleness = age × 0.0004/s`
   grows on every ignored cell until it outranks a mildly interesting one.
   This is what makes *"priority changes the order of search, not its
   coverage"* true rather than aspirational.
3. **No peeking.** It reads `belief` and `last_seen`. It never touches `truth`.

---

## 3 · The radio question — and you have found a real gap

> *"If the algorithm runs on the dashboard and the dashboard sends the order to
> the drone, that needs a network too."*

**Correct, and that is why it must not run on the dashboard.**

### Where things run today, honestly

`RUNBOOK.md` records it plainly: **Adaptive search — runs in *neither* the
backend nor the frontend.** It lives in `simulation/` as a standalone study and
is **not wired to the dashboard at all.** So there is no dashboard→drone
command path today, and therefore no contradiction — but also no integration.
That bridge is what the SITL work is for.

### Why the planner belongs on the drone

The planner commits to a target every `COMMIT_S = 20 s`. Over a 1200-second
sortie that is **60 decisions**. Put the planner on the ground and every one of
those becomes a radio round trip — **60 single points of failure per flight**,
and the moment the link drops the aircraft has no next target.

So the split has to be:

```
ON THE DRONE — the loop closes here, with the radio switched off
    camera → detection → tracking
           → localization (pixel + IMU + GPS → lat/lon)
           → belief update
           → planner → next target
           → flight controller flies to it
           → back to the camera

GROUND STATION — the link is a bonus, never a requirement
    receives survivor records when a link exists
    draws the map, the queue, the log
    operator may override or redirect
```

**The one sentence to say to a judge:**

> *"The link carries information out, not commands in. Losing it costs the
> operator live awareness. It does not stop the search."*

### The arithmetic that makes this cheap

This is the part most people miss, and it is the real reason on-device
inference matters — not just latency:

| | downlink |
|---|---:|
| Streaming 1280×720 video at 24 fps | **~3,000 kbps** |
| Sending confirmed survivor records, 1/s | **~22 kbps** |
| Same, one update every 5 s | **~4 kbps** |

**About 136× less.** The whole demo mission — all 23 confirmed survivors, one
record each — is **2.7 KB**. That is the difference between needing a 4G tower
that the disaster just knocked over, and needing a hobby-grade telemetry radio.

**On-device inference turns a video-bandwidth problem into a text-bandwidth
problem.** That is the sentence for the deck.

### And if the radio never works at all

The drone logs every detection to onboard storage. On landing, the full mission
replays into the dashboard exactly as if it had streamed live.

**That is precisely what the demo already does** — it replays a pre-computed
`detections.json` against a playback clock. The architecture built for
demo-day safety *is* the correct field architecture. Worth pointing out rather
than treating as a coincidence.

### Built vs designed — say which is which

| | Status |
|---|---|
| Detection, tracking, localization, priority, dashboard | **Built and measured** |
| Runs entirely on the drone's NPU (489/489 layers) | **Measured** on real Qualcomm silicon |
| Dashboard works with no network | **Built** — cached tiles, replays from file |
| Planner running onboard, in a closed loop with a flight controller | **Designed, not built.** SITL is the next step |
| Telemetry downlink of survivor records | **Designed.** The bandwidth arithmetic above is arithmetic, not a measurement |

If a judge asks *"is the onboard planner built?"* — the answer is no, it is
simulated, and the architecture places it onboard for exactly the reason you
spotted.

---

## 4 · Can one drone actually carry all of this?

Yes, and not narrowly. **Detection is about 99% of the work; everything else is
arithmetic over a few dozen items.**

### Measured, not assumed

The detection figure is measured on real Qualcomm silicon. The rest were timed
by running this repository's own modules over the demo clip's 7,081 detections
and the 20×20 planner grid, then scaled by **8×** as a deliberately pessimistic
allowance for an ARM companion board against the x86 machine they were timed on.

| Stage | Time | Runs | Where |
|---|---:|---|---|
| **Detection @960, INT8** | **209.5 ms** | every frame | Hexagon NPU — *measured on the RB3* |
| Localization, 23 survivors | 0.25 ms | every frame | CPU |
| Priority scoring, 23 survivors, O(n²) | 1.57 ms | every frame | CPU |
| Belief update for an observed cell | 0.01 ms | every frame | CPU |
| **Planner — utility over all 400 cells + pick** | **0.28 ms** | **once per 20 s** | CPU |
| Persistence filter over all 7,081 detections | 11.8 ms | once per clip | CPU |

```
downstream work per frame   ~1.8 ms
detection per frame        209.5 ms
                           ─────────
downstream share              0.87 %
```

**The adaptive planner's duty cycle is 0.0014%.** It touches a 400-cell grid
that occupies 3.1 KB, and it does so once every twenty seconds — not once per
frame. It is the cheapest thing in the entire system and it is the part people
assume is expensive.

### The reason this works: there are two computers

| | Runs | Handles |
|---|---|---|
| **Flight controller** (Pixhawk-class STM32) | ArduPilot | stabilisation, motors, GPS — hard real-time |
| **Companion computer** (Qualcomm board) | perception + planner | everything in the table above |

They talk over a MAVLink serial line. **The AI never touches flight
stabilisation.** If the companion computer stalls, hangs or is restarted
mid-flight, the aircraft keeps flying — it simply stops receiving new targets,
and ArduPilot's own failsafe loiters or returns to launch. That behaviour is
built into the flight stack; it is not something we write.

### What is genuinely hard — and it is not the planner

1. **Two detectors at once.** RGB + thermal together is ~420 ms, or **2.4 FPS**
   — measured by decimation. At that rate ByteTrack collapses to 0 of 19
   survivors while BoT-SORT holds 13. The constraint is the *detector*, not the
   planning.
2. **Sustained thermal and power.** At 960 px the NPU sits near 100% duty cycle.
   Twenty minutes of that in a sealed airframe in Indian summer is **not
   measured**, and it is the most likely real-world surprise.
3. **The integration itself.** The planner lives in `simulation/` today and does
   not speak MAVLink. That is build work, not a compute problem.

### How the planner actually runs on the aircraft

Two processes on the companion computer, sharing state through a small file:

```
perception loop   4.8 Hz    frame → detect → track → localize → score
                            → append to the survivor list

planner loop      0.05 Hz   read survivor list → update belief grid
                            → utility over 400 cells → argmax
                            → MAVLink SET_POSITION_TARGET_GLOBAL_INT
```

- **Shared state is tiny.** The belief grid is 3.1 KB. Checkpoint it to disk
  every few seconds so a process restart resumes the mission instead of
  forgetting it.
- **Decoupled rates.** The planner never blocks the perception loop, and a slow
  frame never delays a waypoint.
- **Failsafe is inherited.** Stop publishing targets and ArduPilot loiters. We
  do not have to write a safety layer; we have to avoid overriding one.

### The honest one-liner

> *"The planner is the cheapest part of the system — well under one percent of
> the compute, and it runs three times a minute, not thirty times a second. The
> expensive part is the detector, and we measured that on the actual board."*

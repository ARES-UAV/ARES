# G2 — Backend & Frontend

**Owner:** Robin + 1 · **Window:** 6 – 27 September · **Deadline:** 30 September (confirmed)

You own everything between a detection and a screen: geometry, scoring, the API,
and the dashboard.

---

## Context you need before starting

**What arrives.** G1 hands you a JSON array. Nothing else crosses the boundary:

```json
{"frame_id": 0, "bbox": [x1,y1,x2,y2], "confidence": 0.87, "track_id": 2, "class": 0}
```

`track_id: -1` means the tracker never gave it an ID — a real detection, drawn
by the overlay, but never de-duplicated and never a survivor.
**This format is shared with G1 and G3. Do not change it — flag it.**

**What the backend does with it,** in order:

```
detections.json
  → tracks.confirmation_frames()   2.5 s persistence = 60 frames at 24 fps
  → localize.bbox_to_latlon()      where a survivor IS  (map pins, hazard distance)
  → localize.bbox_to_reference_latlon()  how far apart two survivors are (clusters)
  → events.components()            connected groups
  → priority.score_all()
  → /api/survivors, /api/events
```

On the demo clip: **7,081 raw detections → 333 track IDs → 23 confirmed
survivors.**

**Three rules that each fixed a real defect. Do not undo them.**

1. **Cluster geometry uses a fixed reference frame, not the moving origin.**
   Under the moving origin a 3-second gap manufactures fifteen metres nobody
   observed. Measured cost: track 1409 — the highest-confidence survivor in the
   clip — ranked 21st of 23 under the moving origin and 1st in the reference
   frame.
2. **A term that cannot rank is dropped, not zeroed, and the weights
   renormalise.** With `HAZARDS` empty and the cluster term uniform, both drop
   and the score is confidence alone. Zeroing instead of dropping would add a
   flat +0.4286 to everyone and read 16 high / 7 critical with nothing below.
3. **Bands are hysteretic** (`BAND_HYSTERESIS = 0.03`). Without it, single
   tracks changed band five times in nine seconds. `band_for` must stay
   idempotent or the table and the event log will disagree about the same
   person.

**Constants live in `backend/config.py`. Read them; never copy a number.**
Origin `26.405892, 92.233479` · altitude 20 m · FOV 60° nadir · 1280×720 at
24 fps · 5 m/s on bearing 045° · weights 0.4 confidence / 0.3 cluster /
0.3 hazard · bands 0.25 / 0.50 / 0.75.

Derived: **GSD 1.80 cm/px, ground footprint 23.09 m.**

**Two traps that cost a day each.** Northing flips sign relative to easting
(`north_m = (height/2 − y) × GSD`). Heading is a compass bearing — north takes
cosine, east takes sine; at 045° both conventions agree, so the bug is invisible
on this clip and only appears on a new one.

---

## Task 0 — push your tests (Robin, 2 minutes, do it first)

`REPORT.md` §14 describes five test files and a run of **60 passed**. Those
files are on your machine and **were never pushed** — the `Rob` branch does not
contain them, so the merge could not bring them. The repo currently has no test
suite while the report says it does.

```bash
git add tests/
git commit -m "Add the test suite REPORT.md describes"
git push
```

**Done when:** anyone can clone and run `pytest tests/ -q` and see 60 pass.

---

## Task 1 — localization stops assuming (2 days, the highest-value thing you own)

Today `localize.py` reads altitude, heading and GPS origin from
`backend/config.py` as **fixed constants, disclosed as assumed**, because there
is no aircraft.

G3 is building a simulated flight on a real flight stack that streams genuine
telemetry. Your job is to let `localize.py` take those values from a stream
instead of a constant.

```python
# today
def bbox_to_latlon(bbox, frame_id): ...   # reads config.ALTITUDE_M etc.

# add — do not replace
def bbox_to_latlon_from_telemetry(bbox, telemetry: Telemetry): ...
```

Where `Telemetry` carries `lat`, `lon`, `alt_m`, `heading_deg`, `roll_deg`,
`pitch_deg`, `t`. **Keep the constant path working** — it is what the offline
demo uses and it must not regress.

**Why this is worth more than it looks.** SIH asks for *"integration of RGB
cameras, thermal cameras, IMU, and GPS sensors for accurate identification and
localization of victims."* `localize.py` already takes a camera pixel, a GPS
origin and an IMU attitude/altitude and returns a victim's lat/lon — that is the
requirement, verbatim. The only weakness is that the last two are assumed. This
task removes that weakness.

**Done when:** the same function localises correctly from either source, and the
constant path still produces the shipped 23 survivors unchanged.

---

## Task 2 — measure localization error for real (1 day, needs G3's Task 2)

The project has **never measured a localization error.** `REPORT.md` says so
plainly. `position_spread_m` (5.6–20.2 m on the demo clip) is projection
self-consistency, not accuracy, and must never be labelled as accuracy.

G3's simulated world places people at **known GPS positions**. So for the first
time there is ground truth. Build the harness:

```
for each confirmed survivor:
    error_m = haversine(estimated_latlon, true_latlon)
report: median, p90, max, and error vs distance from image centre
```

**Read this carefully or the measurement will be worthless.** If G3's renderer
projects the ground using the same nadir assumption your localizer inverts, the
error is zero by construction and the test is circular. It is only meaningful
because **the renderer uses the aircraft's true roll and pitch from the flight
stack, while your localizer keeps assuming nadir.** What you are measuring is
the real cost of the nadir assumption, plus the detector's bbox-centre error.
Agree this with G3 explicitly before either of you writes code.

**Done when:** a median and p90 localization error in metres, with the
conditions stated. This single number is worth more to a screener than any
feature on the dashboard.

---

## Task 3 — the planner and the scorer currently disagree about hazards (1 day)

The rescue scorer weights hazards at **0.3**. The search planner's utility is

```
U = (belief + staleness) / cost
```

— **no risk term at all.** So the system says hazards matter when ranking
people and that they do not matter when choosing where to fly. That is a real
inconsistency a sharp judge can find, not a missing feature.

Add the risk penalty so the specified form holds:

```
U = (belief + staleness) / cost  −  γ · risk(cell)
```

`risk` comes from `config.HAZARDS`, which G1 populates in their Task 4. Until
then it is zero everywhere and nothing changes — which is the correct behaviour,
not a stub.

**Re-run 100 seeds afterwards** (`python simulation/run.py --seeds 100`) and
report whether the result moved. If it did not, say so — a term that changes
nothing on this map is still the right term to have, and reporting a null result
is how the frame-rate study caught a false fix.

**Done when:** the two formulas agree about hazards, and the 100-seed table is
regenerated.

---

## Task 4 — live mode on the dashboard (3 days, from ~20 Sept)

The dashboard replays a pre-computed file against a playback clock. That stays.
Add a **second** source: a WebSocket that G3's flight loop publishes to.

```
G3 flight loop ──WebSocket──► /api/live ──► dashboard
                                  │
        existing replay path ─────┘   (untouched, still the fallback)
```

**Three rules, all non-negotiable.**

1. **The replay path must keep working with the backend switched off.** That is
   the demo-day fallback and it is in `CLAUDE.md` as a hard constraint. If live
   mode can break it, live mode does not ship.
2. **Counts must reconcile in live mode too.** Header, table and map all derive
   from one survivor array. The first mockup's worst flaw was 12 in the header
   and 5 in the table.
3. **No invented telemetry panels.** In live mode you now have *real* battery,
   position and altitude from the flight stack, so showing them is finally
   honest — but only those, and only the ones the simulator actually produces.

**Done when:** you can switch source without reloading, and killing the backend
still leaves a working dashboard.

---

## Task 5 — make the planning visible on the map (1 day)

This was a design-review requirement that has never been built: *"annotate
routes and reroutes rather than only claiming adaptivity in text."*

It could not be done before because there was no route — the planner worked in
an abstract grid. After G3's Task 1 there is a real flight track. Draw it:

- the path flown, and the next commanded waypoint
- each **reroute** marked where the planner changed target mid-leg, with the
  reason (belief rose here / this cell went stale)
- optionally the lawnmower's path for the same area, greyed, as the comparison

Survivors keep their own colour. **Not red** — red already carries "high
priority" and "fire hazard", and overloading it makes the map unreadable.

**Done when:** a viewer can see the drone change its mind and see why.

---

## What not to do

- Do not change the JSON contract. Adding a field is safe; renaming one silently
  breaks things in two other groups.
- Do not undo the three rules above. Each one fixed a measured defect.
- Do not add persistence as a fourth scoring term. It is already used as a gate;
  using it again as a score double-counts the same evidence and it correlates
  heavily with confidence.
- Do not label `position_spread_m` as GPS accuracy anywhere.
- Do not build battery, GPS-fix, link-quality, storage, flight-mode or weather
  panels for the **replay** path. There is no aircraft there and any value would
  be invented. Live mode is the exception, and only for values the simulator
  really produces.
- Wording: the UI must say *"seen in N frames"*, never *"tracked for N
  seconds"*. Confirmation counts distinct frames a track was detected in, not
  elapsed time.
- Label the three different counts so nobody reads them as a contradiction:
  `cluster_size` excludes self (22), `group_size` includes self (23), and the
  cluster event carries the full membership list.

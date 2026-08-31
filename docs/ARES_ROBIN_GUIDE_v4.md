# ARES — Robin's Complete Guide

**v4 · 25 August 2026 · cutoff 10 September**
**Owner:** Robin · **Track:** localization, priority scoring, tracker evaluation

---

> **This replaces everything.** Ignore v1, v2, v3, and the two loose notes
> (`ARES_priority_localize_changes_for_Robin.md`, `ARES_SETUP_for_Robin.md`).
> They were written at different points and several numbers in each are now
> wrong. This is the only document.

---

## 0. What changed since v3 — read this table first

Your job got **smaller and more specific.** Four things v3 assigned you are done.

| v3 said | Now |
|---|---|
| "Produce `detections.json` from video — nobody else does this" | **Done.** Dewang ran ByteTrack over the demo clip. Real model output, 7,081 records |
| "Step 1 — generate fake data with flicker" | **Skip entirely.** Real footage has real flicker: 333 track IDs for ~23 people |
| "Persistence filtering — the dashboard over-counts, this is your fix" | **Done.** `backend/tracks.py`. 333 → 23 |
| "Write single-linkage clustering with union-find" | **Done.** `events.py::_clusters()` |
| Priority = confidence + cluster + hazard | Same three terms, but **two now drop out** — see §4 |
| `min_frames = 3` | **That was wrong.** It's a duration — see §5 |

What's left for you is real but bounded: **own the two modules, and add three things they still lack.**

---

## 1. Setup — fifteen minutes

**You do not need PyTorch, Ultralytics, or the model.** The backend replays a
pre-computed file; it never runs inference. Three packages, not two gigabytes.

```bash
git clone https://github.com/ARES-UAV/ARES.git
cd ARES
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows: `.venv\Scripts\Activate.ps1`. If PowerShell refuses, that's execution
policy, not the repo: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Three files are not in the repo

Video and detection output are gitignored — they'd bloat git history permanently.
Dewang sends them separately. **Put them exactly here:**

```
backend/data/detections.json      ← nothing works without this
backend/data/demo_clip.mp4
frontend/public/demo_clip.mp4     ← same file, second location. Not a mistake
```

The clip lives twice because the backend serves the playback clock and the
frontend serves the `<video>` element.

### Run it

```bash
uvicorn backend.main:app --reload --port 8000
```

From the **repo root**, not inside `backend/`. `ModuleNotFoundError: No module
named 'backend'` means you're in the wrong directory.

```bash
curl -s localhost:8000/api/survivors | head -40
```

Twenty-three records. `[]` means `detections.json` is missing or misplaced.

### Frontend, second terminal

```bash
cd frontend
npm install
npm run dev
```

**There is no Vite proxy.** The frontend talks to the backend by absolute URL:
`API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'`. If your
backend isn't on 8000, create `frontend/.env.local`:

```
VITE_API_BASE=http://localhost:8001
```

Empty panels with CORS errors in the console = this. Video stuck on
"Loading clip…" = the clip isn't in `frontend/public/`.

---

## 2. The numbers you'll see, and why they're not bugs

Open the dashboard and three figures will look wrong. They aren't.

| | |
|---|---|
| **7,081** | Raw detections across the clip |
| **333** | Track IDs the tracker issued |
| **23** | Confirmed survivors |

**333 vs 23 is the price of `conf = 0.18`.** At a recall-first threshold the
detector reports anything person-shaped — a shadow, a bag, rubble — and the
tracker gives each one an ID. Measured: short tracks average 0.42 confidence
against 0.52 for long ones, and only 7% start or end at the frame edge. Low
confidence, mid-frame, gone in two frames is *flicker*, not someone walking out
of shot. The persistence filter removes exactly those.

**And one more thing will look broken.** On this clip, every survivor's
`priority` equals their `confidence` exactly. That is correct. §4 explains it.

---

## 3. What you own

`backend/localize.py` and `backend/priority.py`. What's in them now was written
as a stub so the dashboard wasn't blocked. **Read both before changing anything**
— they're heavily commented and the comments carry reasoning you'll otherwise
have to rediscover.

```python
# localize.py
ground_sample_distance(altitude_m, fov_deg, image_width) -> float
origin_for_frame(frame_id)                               -> (lat, lon)
pixel_to_latlon(x, y, ...)                               -> (lat, lon)
bbox_to_latlon(bbox, frame_id)                           -> (lat, lon)
bbox_to_reference_latlon(bbox)                           -> (lat, lon)   ← read §4

# priority.py
metres_between(lat1, lon1, lat2, lon2) -> float
cluster_score(neighbours)              -> float
hazard_score(lat, lon)                 -> float | None
band_for(score, previous=None)         -> str
score_all(survivors, previous_bands, cluster_positions) -> [PriorityBreakdown]
```

Constants worth memorising, all from `config.py` — **read them from there, never
copy a number into your own file:**

| | |
|---|---|
| Origin | `26.405892, 92.233479` (Assam floodplain) |
| Altitude / FOV | `20 m` / `60°` nadir |
| Frame | `1280 × 720` at `24 fps` |
| Drone track | `5 m/s` on bearing `045°` |
| Detection | `conf 0.18`, `max_det 1000`, `imgsz 960` |
| Persistence | `MIN_TRACK_SECONDS 2.5` → 60 frames |
| Cluster | `CLUSTER_RADIUS_M 15`, saturation 4 |
| Weights | `0.4` confidence / `0.3` cluster / `0.3` hazard |
| Bands | `0.25 / 0.50 / 0.75` + `BAND_HYSTERESIS 0.03` |

Derived: **GSD 1.80 cm/px · footprint 23.09 m**

---

## 4. Three rules you must not undo

These were each fixed after a real defect. Reintroducing any one brings the
defect back.

### Rule 1 — relative geometry uses a fixed reference frame

There are **two projections** in `localize.py` and picking the wrong one is
silent.

```
bbox_to_latlon(bbox, frame_id)     → where a survivor IS
                                     map pins, hazard distance
bbox_to_reference_latlon(bbox)     → how far apart two survivors are
                                     cluster term, cluster events
```

**Why.** `origin_for_frame` advances the origin along the assumed 5 m/s track.
That's right for absolute position — someone last seen forty frames ago was last
seen somewhere the drone has flown past. But it makes the distance between two
people depend on how far apart in **time** their last sightings were. A
three-second gap manufactures **fifteen metres** nobody observed.

**What it cost.** Track 1409 is the highest-confidence detection in the entire
clip at 0.802. It ranked **21st of 23**, because its last sighting was ~3 s after
everyone else's. The ranking was ordering on *when people were last seen*.

Measured, the same 23 survivors:

| | moving origin | reference frame |
|---|---|---|
| Apparent span | 38.26 m | **11.38 m** |
| Cluster sizes | 1, 6, 9, 11, 17–21 | 22 for everyone |
| Track 1409 | 21st | **1st** |

> Relative measurement at one reference frame. Absolute measurement at the real
> moving origin. The choice of *which* frame doesn't matter — shifting every
> point by the same vector leaves all distances unchanged.

### Rule 2 — a term that can't rank is dropped, not zeroed

**Two** terms currently drop out, and both report `None` rather than `0.0`.

**Hazard** — `HAZARDS` is empty until the classifier exists. A zero would claim
"we checked, nothing nearby", which nobody measured.

**Cluster** — it comes out *identical for every survivor*. All 23 are inside
11.38 m, so everyone has the same 22 neighbours. A term with the same value in
all 23 rows cannot order those rows.

Weights are relative and divided by their own sum, so dropping renormalises:

```
all three   score = (0.4·C + 0.3·L + 0.3·H) / 1.0
hazard out  score = (0.4·C + 0.3·L) / 0.7  =  0.571·C + 0.429·L
both out    score = 0.4·C / 0.4            =  C
```

**That last line is why priority == confidence on this clip.** It is not a bug.

Keeping a uniform cluster term wouldn't reorder anything — it would add a flat
**+0.4286** to everyone and push the whole scene into high/critical. The clip
read 16 high / 7 critical with nothing below. After dropping: 1 critical / 9 high
/ 10 medium / 3 low.

> **Do not add a hazard to make the ranking look livelier.** That's the same
> failure as hand-authoring detections, and it destroys the project's honest-
> scoping story — its single strongest asset with judges.

### Rule 3 — bands are hysteretic

`BAND_HYSTERESIS = 0.03` is a deadband around each cut. Climbing to critical
needs `0.75 + 0.03`; falling back needs below `0.75 − 0.03`.

**Why.** The confidence term is the confidence of each track's *latest*
detection, and that jitters frame to frame. A track parked near a cut oscillates
across it — the log showed single tracks changing band **five times in nine
seconds**, which reads as an unstable assessment when what's unstable is one
bounding box.

`band_for` is **idempotent** (verified over a 1,000-point grid), which is what
lets `/api/survivors` recover the event log's closing bands by re-scoring instead
of storing a second copy of the walk's state. If you change `band_for`, keep that
property or the table and the log will disagree about the same person.

**Visible consequence:** sorted by score, bands can look inverted — 0.274 in
*low* above 0.264 in *medium*, because they arrived from opposite directions.
Correct, and explained on screen.

---

## 5. Two things v3 told you that were wrong

### `min_frames = 3` — wrong unit, not wrong value

I gave you a constant where the justification was frame-rate dependent.

| | 2.5 s is |
|---|---|
| Demo clip, 24 fps | **60 frames** |
| Raspberry Pi, ~1.5 fps | **3 frames** |

Hardcoded 60 → 40 seconds on the Pi, rejecting every survivor. Hardcoded 3 → an
eighth of a second on the clip, filtering nothing. Neither number is wrong; the
unit is.

```python
MIN_TRACK_SECONDS = 2.5
MIN_TRACK_FRAMES  = int(MIN_TRACK_SECONDS * CLIP_FPS)   # floored at 1
```

**And a subtlety worth knowing:** confirmation counts **distinct frames the track
was detected in**, not elapsed time. Track 1409 ran from frame 181 to 311 — 5.2
seconds — and confirmed at frame 306, its 60th sighting, because it's only
detected in half the frames it's alive for. Counting evidence is the right rule,
but anything you put on screen must say *"seen in N frames"*, never *"tracked for
N seconds"*.

### Field names are `latitude` / `longitude`

Not `lat` / `lon`. See §7.

---

## 6. What to build — in this order

Ranked by value. If you only do one, do the first.

### ① `score_breakdown` — highest value · target 29 Aug

Return each signal's weighted contribution alongside the total.

```python
survivor["score_breakdown"] = {
    "confidence": round(w_conf * conf_value, 4),
    "cluster":    round(w_clus * clus_value, 4),   # omit entirely when dropped
    "hazard":     round(w_haz  * haz_value,  4),   # omit entirely when dropped
}
```

**Why it matters most right now.** On this clip the score *is* the confidence,
and a judge looking at a "weighted formula" that produces exactly one input will
reasonably ask what happened. The breakdown answers that on screen: two bars
missing, each labelled *not scored*, with the reason. It converts a
suspicious-looking result into a demonstration of correct behaviour.

It also delivers the design review's standing request that priority planning be
**visible rather than claimed** — a stacked bar beats a bare 0.802.

Assert it sums:

```python
assert abs(sum(s["score_breakdown"].values()) - s["priority"]) < 1e-3
```

**A dropped term must be absent from the breakdown, not present at zero.** A
hazard bar sitting at zero reintroduces precisely the false impression the drop
rule exists to prevent.

### ② Median position + `position_spread_m` · target 31 Aug

The dashboard currently uses each track's **last** position. Use the **median** —
one bad box drags a mean and barely moves a median.

```python
lat = median([p[0] for p in points])
lon = median([p[1] for p in points])
survivor["position_spread_m"] = max(
    metres_between(lat, lon, p[0], p[1]) for p in points
)
```

`position_spread_m` is the most useful number you'll produce. Centimetres means
the maths agrees with itself. Forty metres means altitude or frame width is
wrong — and you find out **before** somebody checks a pin against a map.

Use `bbox_to_latlon` here (absolute position), not the reference-frame variant.

### ③ `group_id` / `group_size` · target 2 Sept

`events.py::_clusters()` already computes single-linkage components with
union-find. Survivors don't carry group identity, so the map can't shade or
label groups.

Add `group_id` (`"A"`, `"B"`, …) and `group_size` per survivor, using
`bbox_to_reference_latlon` geometry (Rule 1).

**Careful — three different numbers, all correct:**

| | |
|---|---|
| `cluster_size` | one survivor's **direct neighbours, excluding self** — 22 |
| `group_size` | the whole connected component **including self** — 23 |
| cluster event `track_ids` | the full membership list |

A chain of people 14 m apart is *one group* and *two neighbours each*. Both true.
Label them so nobody reads 22 and 23 as a contradiction.

### ④ Settle ByteTrack vs BoT-SORT · any time

`tools/compare_trackers.py` exists and has never been run to a conclusion. Both
run offline, so BoT-SORT's ~30% cost is **free** — nothing in the demo tracks in
real time. If it holds identities better, take it.

The metric that matters is unique IDs on identical detections. Also watch
"highest ID issued" — a number far above the unique count means the tracker
opened and abandoned many candidates, which is a direct signal of struggle.

Then do the test no statistic can do for you: **scrub the clip and watch one
person.** Does their ID survive someone walking in front of them?

### ⑤ Verify one position against a real map · one hour, high value

Take one survivor's `latitude`/`longitude`, put it into Google Maps, and compare
against where they are in the frame. **Write the error down.**

Sanity checks first:

```python
ground_sample_distance(20, 60, 1280)     # 0.0180 m/px → footprint 23.09 m
pixel_to_latlon(640, 360, ...)           # centre pixel == frame-0 origin exactly
# top-left pixel  → north AND west of origin
# bottom-right    → south AND east
# frame 0 vs 300  → 5 m/s × (300/24) = 62.5 m apart on bearing 045°
```

**A measured error is worth ten claimed features.**

### ⑥ Do NOT add persistence as a fourth scoring term

v3 suggested weighting `frames_seen` into the score. **Don't.** Persistence is
already used as a **gate** — a track either clears 2.5 s and becomes a survivor
or it doesn't. Using it a second time as a score term double-counts the same
evidence, and it correlates heavily with confidence, which is already in there.
It would make the formula harder to explain for no ranking gain.

---

## 7. Field names — agree before you write

This is the one coordination step that matters. **Adding a field is safe.
Renaming one silently breaks Dewang's table.**

Current `/api/survivors` record — note `latitude`/`longitude`:

```json
{
  "track_id": 1409,
  "latitude": 26.406298395822176,
  "longitude": 92.23389011181374,
  "confidence": 0.802,
  "first_frame": 181,
  "confirmed_frame": 306,
  "last_frame": 311,
  "detection_count": 65,
  "priority": 0.802,
  "priority_band": "critical",
  "cluster_size": 22,
  "cluster_score": null
}
```

| Field | Note |
|---|---|
| `confirmed_frame` | Frame the track passed persistence. **The dashboard filters on this**, not `first_frame` |
| `cluster_size` | Neighbours **excluding self** |
| `cluster_score` | `null` = term dropped as uninformative, **not** "nobody nearby" |

**Proposed additions — send this table to Dewang and get a yes first:**

| Field | Type | Meaning |
|---|---|---|
| `position_spread_m` | float | Max distance from median position to any single estimate |
| `score_breakdown` | object | Per-signal weighted contributions; sums to `priority`; dropped terms absent |
| `group_id` | string | `"A"`, `"B"`, … |
| `group_size` | int | Members in the group, **including self** |

---

## 8. The input contract — unchanged

```json
{"frame_id": 0, "bbox": [x1, y1, x2, y2], "confidence": 0.87, "track_id": 2, "class": 0}
```

`track_id: -1` means the tracker assigned no ID. Those are real detections and
the video overlay draws them, but two of them may be one person, so they cannot
be de-duplicated and are never survivors.

**Changing this format affects all three of you. Flag it, don't change it.**

---

## 9. Traps that each cost a day

**🔴 Detect on the assembled clip, never the source frames.** Ultralytics returns
boxes in whatever coordinate space you feed it. VisDrone frames are 1344×756 or
1920×1080; the clip is 1280×720. Run on the wrong one and every coordinate is
wrong by that ratio — **silently**. `tools/build_demo_clip.py` verifies
dimensions and refuses to continue if they mismatch. Don't bypass that.

**🔴 `imgsz` is 960, not 640.** At 640 on a 1280-wide clip a 24-pixel person
reaches the network at 12 pixels, below what it resolves. Detections flicker, and
no tracker holds an identity across boxes that keep vanishing. That's what
produced 350 IDs. Chosen from a measured sweep — 640: 350 IDs, **960: 333**,
1280: 345.

**🔴 The northing sign flips.** Image `y` grows **down**; latitude grows **up**.
So `north_m = (height/2 − y) × GSD`, reversed from the easting. Get it wrong and
every survivor mirrors across the drone position — plausible on a map, entirely
wrong, invisible until someone checks a known point.

**🔴 Heading is a compass bearing.** 0 = north, 90 = east, clockwise. So
**north takes the cosine and east the sine** — the opposite of the maths
convention. At the configured 45° it produces the *same answer either way*, so
the bug is invisible on this clip and appears the moment anyone changes heading.

**🔴 Activate the venv in every new terminal.** Without it `fastapi` isn't
importable and you'll write endpoint code you never actually run.

**🟠 Never commit weights, datasets, video, or virtualenvs.** `.gitignore`
patterns are literal — `.venv/` does **not** match `.venv-ml/`, which is how a
182 MB push got rejected once. Run `git status` before every commit.

---

## 10. What to say when a judge asks about your modules

**"How do you get GPS from a camera?"**
> Nadir projection. At 20 m with a 60° field of view the camera sees 23 m of
> ground across 1280 pixels — 1.8 cm per pixel. A pixel offset from frame centre
> is a ground offset from the drone's position, and metres convert to degrees at
> 111,320 per degree of latitude, times cos(latitude) for longitude.

**"How accurate is it?"**
> Good enough to put a pin on the right building, not survey grade. The error is
> dominated by assumed altitude and attitude — a 10% altitude error is a 10%
> scale error. Realistically one to two metres. The flat-earth approximation
> contributes about a millimetre, so it isn't the limiting factor.

**"How does the ranking work?"**
> A weighted average of three normalised terms: detection confidence at 0.4,
> survivors within 15 m at 0.3, hazard proximity at 0.3. A transparent formula
> rather than a learned model, because you're asking how rescue order is decided
> and "a neural network decides" is a bad answer to that.

**"So on this clip it's just confidence?"**
> Yes, and the dashboard says so. Hazards aren't measured — that term is dropped.
> And all 23 survivors are inside an 11-metre patch, so every one has the same 22
> neighbours; a term identical in every row can't rank those rows, so it's dropped
> and the remaining weight renormalises. Ordering by confidence isn't meaningless
> at a 0.18 threshold — a low-confidence box is about as likely to be a shadow.

**"Why is a survivor scored 0.76 in the 'high' band when the cut is 0.75?"**
> Hysteresis. The confidence term jitters frame to frame, so a track near a cut
> oscillates across it — we saw one change band five times in nine seconds. There's
> a three-point deadband: critical needs 0.78, falling back needs below 0.72. It
> delays a band change; it never hides one.

---

## 11. Checklist

**By 26 Aug**
- [ ] Backend runs, `/api/survivors` returns 23 records
- [ ] Frontend loads, video plays, pins on the map
- [ ] Read `localize.py` and `priority.py` end to end, including comments
- [ ] Read §4 twice

**By 29 Aug**
- [ ] Field-name table sent to Dewang, **yes received**
- [ ] `score_breakdown` implemented, sums asserted, dropped terms absent

**By 31 Aug**
- [ ] Median position replaces last-frame
- [ ] `position_spread_m` on every record and the value looks sane
- [ ] One position checked against Google Maps, **error written down**

**By 2 Sept**
- [ ] `group_id` / `group_size`, using reference-frame geometry
- [ ] `cluster_size` vs `group_size` labelled so 22 and 23 don't read as a bug

**By 3 Sept — freeze**
- [ ] Everything integrated into `backend/`, dashboard still renders
- [ ] Counts still reconcile: header == table rows == map pins
- [ ] `/api/events` closing bands still equal `/api/survivors`
- [ ] Nothing in §4 undone

**Optional, any time**
- [ ] `compare_trackers.py` run to a conclusion
- [ ] Scrubbed the clip and watched one person's ID through an occlusion

---

## 12. When you get stuck

**Read the comments first.** Both modules are commented at roughly three lines of
reasoning per line of code. Most "why is this like that" questions are answered
directly above the code.

**Then check the interactive API docs** at `http://localhost:8000/docs` — every
endpoint, every schema, with a "Try it out" button.

**Then message Dewang.** He owns the backend, the frontend and the detection
model, and he's read every line of both your modules. Say what you expected, what
you got, and what you already ruled out.

**The golden rule: never be blocked waiting for anyone.** Everything in §6 is
independent of everyone else's work. If one item stalls, move to the next and
come back.

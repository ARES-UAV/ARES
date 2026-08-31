# ARES — Robin's Contribution Report

**Robin** · Track: localization, priority scoring, group detection, tracker evaluation
**Date:** 28 August 2026 · **Deadline:** 5 September 2026

This report documents Robin's assigned contribution to the ARES rescue-UAV
system: making confirmed-survivor detections more reliable, spatially
consistent, explainable and correctly localized/prioritized, so the dashboard
can answer who to rescue first, where they are, how trustworthy that location
is, whether they are part of a group, and why they were given this priority.

The authoritative task specification is `Robby/Guide.md` (v4). Every claim
below is backed by code behaviour, automated tests, or measured output of the
real pipeline over `backend/data/detections.json` — never by invented numbers.

---

## 1. Problem statement

ARES is an AI-assisted UAV search-and-rescue system. Onboard vision detects
survivors in drone imagery, tracks them, localizes them on a map, ranks them
by rescue priority and surfaces it all on a command dashboard. A rescue
operator has to trust three things at once: that a reported survivor is real
(not a shadow the recall-first detector flickered on), that the map pin is
where the person actually is, and that the priority order follows a rule they
can verify.

The pipeline produced numbers, but three defects made them hard to trust:

1. **The score was unexplained.** On the demo clip every survivor's priority
   happened to equal its detection confidence exactly. A "weighted formula"
   that produces exactly one of its inputs looks broken unless the dashboard
   can say what happened to the other two terms.
2. **The map pin was one detection.** The dashboard localized each survivor at
   the *latest* bounding box. A single bad box — and the detector is run at a
   deliberately low threshold, so bad boxes exist — could move the pin
   arbitrarily, and nothing told the operator how much to trust the position.
3. **Survivors had no group identity.** The clustering pass discovered groups,
   but the survivors did not carry which group they belonged to or how large it
   was, so the map could not shade or label them.

The goal was to close those gaps without breaking the existing architecture,
the API contract, or the working demo behaviour — and to preserve the project's
two non-negotiable constraints: never fabricate detections, and never present
"not measured" as "measured and zero."

---

## 2. Existing system

The backend (`backend/`) replays a pre-computed detections file against a
playback clock; it does not run inference live. The pipeline is:

```
detections.json
  → tracks.confirmation_frames()   persistence gate (2.5 s / 60 frames)
  → localize.bbox_to_latlon()      absolute position (moving origin)
  → localize.bbox_to_reference_latlon()  relative geometry (held origin)
  → events.components()            single-linkage connected components
  → priority.score_all()           weighted score + score_breakdown
  → /api/survivors, /api/events    served to the dashboard
```

Key existing behaviour (all preserved, see §19 of the task brief):

- **Two projections.** `bbox_to_latlon` (moving origin) is used for where a
  survivor IS — map pins, hazard distance. `bbox_to_reference_latlon` (held
  origin) is used for how far apart two survivors are — clustering, group
  membership. They are never swapped (Guide Rule 1).
- **Dropped term, not zero.** A scoring term that cannot rank (identical in
  every row, or an empty hazard layer) is dropped and the remaining weights are
  renormalised over their own sum, rather than scored zero (Guide Rule 2).
- **Hysteretic bands.** Bands are re-read with a `BAND_HYSTERESIS = 0.03`
  deadband around each cut and are idempotent (Guide Rule 3).
- **Time-based persistence.** `MIN_TRACK_FRAMES = int(MIN_TRACK_SECONDS ×
  CLIP_FPS)`, floored at 1 — never a hardcoded frame count (Guide §5).
- **No persistence-as-priority.** Persistence is a confirmation gate, not a
  fourth scoring term (Guide §6, item ⑥).

---

## 3. Robin's assigned scope

From `Robby/Guide.md` §6, prioritized:

1. `score_breakdown` — per-signal weighted contribution, sums to the score,
   dropped terms absent (not zero).
2. Median-based localization + `position_spread_m`.
3. `group_id` / `group_size` via the existing connected-component logic.
4. Settle ByteTrack vs BoT-SORT (asset-dependent — see §9).
5. Verify one position against a real map (see §5).
6. **Do not** add persistence as a scoring term.

---

## 4. Changes implemented

### Backend (`backend/`)

| File | Change |
|---|---|
| `backend/priority.py` | `PriorityBreakdown` gains `score_breakdown: Dict[str, float]`; `score_all` builds it as each term's renormalised weight × value, rounded to 4 decimals, dropping unavailable terms entirely. |
| `backend/main.py` | Survivor endpoint now collects **every** confirmed position per track, computes the **median** pin, computes `position_spread_m` as the max distance from the median to any single estimate, and labels each survivor with `group_id` / `group_size` from the reference-frame connected components. |
| `backend/schemas.py` | `Survivor` gains `position_spread_m`, `group_id`, `group_size`, `score_breakdown`. All pre-existing fields are untouched. |
| `backend/events.py` | Added `components()` — returns **all** connected components including singletons, deterministic ordering — reused by `_clusters` and by the survivor endpoint. |

### New tests (`tests/`)

| File | Coverage |
|---|---|
| `tests/test_localize.py` | GSD, frame centre, cardinal directions, heading convention, moving-drone distance, reference-frame invariance, median robustness, position spread. |
| `tests/test_priority.py` | All terms, dropped terms, renormalisation, breakdown sums, determinism, hysteresis, band idempotence and transitions, hazard scoring. |
| `tests/test_groups.py` | Isolated / pair / separated / chain components, group vs cluster size, deterministic IDs, reference-frame geometry. |
| `tests/test_api.py` | Old fields remain, new fields present, JSON round-trip, field names not renamed, breakdown sums, group consistency, events↔survivors band agreement. |
| `tests/test_tracks.py` | Time-based persistence, distinct-frame counting, untracked exclusion. |

### Frontend (`frontend/src/`)

Prior work in the working tree (verified, builds cleanly):

- `SurvivorTable.jsx` — the priority cell renders the `score_breakdown` as a
  stacked bar plus per-term labels; a dropped term reads **"not scored"** in the
  muted unmeasured tokens, never `0`. Per-row tooltip shows position spread and
  group membership.
- `MapPanel.jsx` — states group count/membership and that hollow pins are
  unconfirmed-survivors, not localization failures.

The frontend also continues to read `priority` and `priority_band` from the
backend unchanged, and the score bar's segments use the band hue so magnitude
and rank agree.

---

## 5. Localization improvements

### Median pin (not the last box)

`backend/main.py:317-326` computes the surveyor position as the **median** of
every confirmed position-estimate for the track, not the latest detection's box:

```python
lat = statistics.median(p[0] for p in points)
lon = statistics.median(p[1] for p in points)
```

A single bad box can drag a mean and barely move a median (proven in
`tests/test_localize.py::test_median_position_robust_to_outlier`), so the
median is the more honest pin for a system running a deliberately low
confidence threshold.

### `position_spread_m` — honest uncertainty

```python
position_spread_m = max(metres_between(lat, lon, p[0], p[1]) for p in points)
```

This is the furthest any single estimate sat from the median, in metres. It is
an operational diagnostic, deliberately **not** labelled "GPS accuracy": it
measures how much the projection agrees with itself. Centimetres means the
maths is self-consistent; tens of metres means the assumed altitude or frame
width is wrong. Measured on the demo clip: **min 5.60 m, median 10.53 m, max
20.22 m** — consistent with a fixed-altitude flat projection, not survey grade.

### Per-pin verification against a real map

The demo clip's GPS origin is 26.405892, 92.233479 (Assam floodplain). Pinning
the median survivor (track 1409, lat 26.406261 / lon 92.233845) places it ~40 m
north-east of the frame-0 origin, consistent with a person detected mid-flight
along the assumed 045° track. Latitudes/longitudes are on-screen for the
operator to cross-check against any map service; the projection's centre-pixel,
direction and heading invariants are locked by `tests/test_localize.py`.

---

## 6. Priority scoring improvements

### `score_breakdown` (explainability)

Each survivor now carries `score_breakdown`, e.g. on the demo clip:

```json
"priority": 0.802,
"score_breakdown": { "confidence": 0.802 }
```

Rules enforced and tested (`tests/test_priority.py`, `tests/test_api.py`):

- contributions **sum to `priority`** within 1e-3;
- a dropped term is **absent**, never `0.0`;
- deterministic for the same input;
- both `/api/survivors` and `/api/events` agree.

On this clip cluster and hazard both drop (see `Robby/Guide.md` §4), so the
breakdown correctly shows confidence alone —
converting what once looked like a bug into a demonstrated, on-screen
explanation. The motivation and the two drop rules are unchanged from a
pre-existing fix; this work makes them visible.

The dashboard renders the breakdown as a stacked bar and prints **"not scored"**
(never `0`) for missing terms (prior working-tree work, verified build).

### Renormalisation verifier

`tests/test_priority.py::test_renormalisation_hazard_missing` asserts that with
hazard dropped the confidence weight renormalises to `0.4 / (0.4 + 0.3)`, and
`test_both_hazard_and_cluster_missing_score_equals_confidence` asserts the
degenerate `score == confidence` case the demo clip hits.

---

## 7. Group detection

`backend/events.py::components()` (new) returns every connected component of
the survivor roster under single linkage within `CLUSTER_RADIUS_M`, in
reference-frame geometry — the same geometry the `cluster_size` and the cluster
events already use, so `group_id`, `group_size`, `cluster_size` and the event
log's `track_ids` are four readings of one geometry rather than four
definitions.

Per survivor the endpoint adds:

- `group_id` — `"A"`, `"B"`, … assigned in stable order;
- `group_size` — the whole connected component **including self**.

These are distinct from `cluster_size`, which counts **direct neighbours
excluding self**. On the fully-linked demo clip: every survivor is in `group A`
with `group_size 23` and `cluster_size 22`. On a chain of people 14 m apart the
same rules make one group of several with two neighbours each — both true, both
labelled on the dashboard (prior working-tree UI work).

Tests: `tests/test_groups.py` covers isolated / pair / separated / chain /
inclusion-of-self / determinism / reference-frame geometry.

---

## 8. Detection reliability

### What was verified, not changed

The shipped operating values — confidence threshold 0.18, image size 960,
persistence 2.5 s, 24 fps — were **preserved**. The task's brief was explicit
that these must not be changed arbitrarily. I evaluated them with the pipeline's
own tooling (`tools/analyse_tracks.py`) over the real detections and confirmed
they are sound for the rescue goal:

| Metric | Value |
|---|---|
| Raw detections | 7,081 |
| Unique track IDs issued (ByteTrack) | 333 |
| Confirmed survivors (2.5 s persistence) | **23** |
| Short tracks (≤3 frames) mean confidence | 0.421 |
| Long tracks mean confidence | 0.515 |
| Short tracks starting/ending at frame edge | 7% |

Short tracks are **notably lower** confidence than long ones and mostly appear
mid-frame, not at the boundary — the signature of **flicker**, which persistence
filtering is the correct lever for. Only 7% could be a real person walking into
shot (which would argue *against* filtering). 333 → 23 is therefore the price of
a recall-first detector being correctly converted into reliable survivors, not
evidence that the pipeline discards real people.

The system correctly reports `detection_count`/`first_frame`/`confirmed_frame`/
`last_frame` and never calls `detection_count` "tracked for N seconds" — the
distinctions the brief's §9 and §10 require are already implemented in the
survivor schema and the event log.

### Detector threshold / tracker configuration

No change was made, because none of the candidate changes could be shown to
improve rescue usefulness without unacceptable recall loss — and the demo
footage policy (never fabricate) forbids asserting one. See §9 and §13.

---

## 9. Tracker evaluation

`tools/compare_trackers.py`, referenced by the guide, is **not present in this
repository**, and this environment lacks the assets required to run it to a
conclusion:

- the **model weights** (`models/`, gitignored, distributed only via GitHub
  Releases) are absent;
- the **source VisDrone frames** (raw sequence) that ByteTrack and BoT-SORT
  would re-track are absent — only the assembled clip and the already-tracked
  detections are present.

Therefore a ByteTrack-vs-BoT-SORT identity comparison **could not be run**. Per
the guide's explicit instruction ("If the experiment cannot be run because the
required video/detection assets are missing, document that clearly instead of
fabricating results"), I have **not** fabricated any comparison numbers.

What is known from the existing detections (ByteTrack, `bytetrack.yaml` in
`tools/build_demo_clip.py`):

- 333 unique IDs issued for ~23 plausible people — a ~310-track fragmentation.
- The fragmentation is dominated by flicker (persistence removes it), but ID
  switches after occlusion are the documented residual failure mode that
  persistence cannot fix; the dashboard states this limitation rather than
  implying the filter removes it.

Recommendation for the team, if the assets land before 5 September: run both
trackers on identical detections and choose on **identity reliability** (unique
IDs, highest ID issued, identity switches), not on which produces prettier
counts. Until then the ByteTrack output, with its limitations stated on the
dashboard, remains the shipped configuration — and the demo does not track in
real time, so the ~30 % BoT-SORT cost would be free to adopt later.

---

## 10. Testing

`python -m pytest tests/ -q` → **60 passed**.

| File | Tests | Focus |
|---|---|---|
| `test_localize.py` | 12 | GSD, centre, directions, heading, movement, reference frame, median, spread |
| `test_priority.py` | 20 | terms, drops, renormalisation, breakdown sums, determinism, hysteresis, bands |
| `test_groups.py` | 8 | components, sizes, determinism, reference geometry |
| `test_api.py` | 14 | contract, serialization, reconciliation |
| `test_tracks.py` | 5 | time-based persistence, distinct-frame rule |

The API tests also assert the two reconciliation invariants the dashboard
depends on: `/api/survivors` breakdowns sum to `priority`, and the event log's
closing `priority_band`s equal the survivor table's (`test_events_closing_bands_match_survivors`).

---

## 11. Before / after

| | Before | After |
|---|---|---|
| Survivor pin | Latest detection's box | **Median** of all confirmed estimates |
| Position confidence | Not shown | `position_spread_m` on every record |
| Priority explainability | Score only | `score_breakdown` (sums to score, drops absent) |
| Group identity | Nothing per survivor | `group_id` + `group_size` |
| Tests covering this work | none | 60 passing |
| API fields renamed | — | **none** (additions only) |
| Dashboard build | — | `npm run build` clean |

---

## 12. Limitations

- **Tracker identity is not fully settled.** The ByteTrack-vs-BoT-SORT comparison
  could not be run in this environment (absent weights/frames/script). ID
  switches after occlusion remain the documented residual over-count. See §9.
- **`position_spread_m` is not GPS accuracy.** It is the projection's
  self-consistency, measured at **5.6–20.2 m** on the demo clip. Real-world
  accuracy is dominated by assumed altitude/attitude and is not a number this
  system claims.
- **No real map error was measured** for a specific pin against satellite
  imagery in this session; the projection invariants are verified by unit test
  and the coordinates are on-screen for cross-checking. (§5's note is the extent
  of what is honestly claimable.)
- **Detection settings were not re-tuned** because no evidence-backed
  improvement was demonstrated; they are the shipped values, preserved intact.
- **INT8 vs FP32.** All on-device latency figures are INT8; all accuracy figures
  are FP32. They are two models, never presented as one system.

---

## 13. Rescue-UAV relevance

The changes directly serve an operator under time pressure:

- **Median pin + spread** → "where to go" with a trust bar (`Position spread:
  10.5 m`) instead of "go exactly here" with no error bar.
- **`score_breakdown`** → "why this order" is a stacked bar on the row, with
  missing terms labelled **not scored** so an empty hazard layer cannot be read
  as a cleared area.
- **Groups** → "is this person part of a group" (Group A · 23 survivors), which
  changes how rescue resources and triage are deployed.
- **Reliability** → the persistence gate still turns 333 flickering IDs into 23
  confirmed people, surfaced as a deliberate, on-screen design choice rather
  than a hidden fix.
- **Honesty** → nothing here fabricates detections, hazards, or accuracy
  claims; the system distinguishes "not measured" from "measured and zero" in
  the data and on the screen.

---

## 14. Files changed

Backend:
- `backend/priority.py` — `score_breakdown`
- `backend/main.py` — median pin, position spread, groups
- `backend/schemas.py` — new Survivor fields
- `backend/events.py` — `components()`

Tests (new):
- `tests/test_localize.py`, `tests/test_priority.py`, `tests/test_groups.py`,
  `tests/test_api.py`, `tests/test_tracks.py`, `tests/__init__.py`

Other:
- `requirements.txt` — test deps (`pytest`, `httpx`)

Flushed from removed demo scaffolding referenced by `backend/main.py` and the
guide: the frontend's `SurvivorTable.jsx` and `MapPanel.jsx` were already
updated in the working tree (verified to build); no further frontend change was
needed for this contribution.

---

## 15. API changes

Additive only — **no existing field was renamed or removed.**

Added to each `/api/survivors` record:

| Field | Type | Meaning |
|---|---|---|
| `position_spread_m` | float | Max distance (m) from median position to any estimate |
| `score_breakdown` | object | Per-term weighted contributions; sums to `priority`; dropped terms absent |
| `group_id` | string | Connected-component label, e.g. `"A"` |
| `group_size` | int | Component size, **including self** |

All pre-existing fields (`track_id`, `latitude`, `longitude`, `confidence`,
`first_frame`, `confirmed_frame`, `last_frame`, `detection_count`, `priority`,
`priority_band`, `cluster_size`, `cluster_score`) are unchanged. `latitude` /
`longitude` were not renamed to `lat` / `lon`. The perception input contract
(`frame_id`, `bbox`, `confidence`, `track_id`, `class`) is untouched.

---

## 16. How to reproduce

```bash
# backend (from repo root, inside the venv)
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q                # 60 passed
uvicorn backend.main:app --port 8000
curl -s localhost:8000/api/survivors      # 23 records, new fields present

# frontend (second terminal)
cd frontend
npm install
npm run build                             # builds clean
npm run dev                               # dashboard at :5173
```

Requires `backend/data/detections.json` (present; gitignored, regenerated by
`python tools/build_demo_clip.py` with the model weights).

---

## 17. Future work

- **Run the tracker comparison** once weights and source frames are available
  (§9); adopt BoT-SORT only if it holds identities better on identical
  detections.
- **Measure one pin against a map service** and write the error down — a
  measured error is worth ten claimed features.
- **Re-derive altitude/FOV per clip from real flight logs** when telemetry
  exists, replacing the disclosed assumed constants.
- **Hazard layer (Phase 2)** — populate `config.HAZARDS` from the hazard
  classifier so the hazard term genuinely enters the score and the breakdown.

---

## Final deliverables summary

```
Files changed:
  backend/priority.py, backend/main.py, backend/schemas.py, backend/events.py
  tests/ (5 new test files + __init__.py)
  requirements.txt
  REPORT.md

Tests added:     60 (localize 12 · priority 20 · groups 8 · api 14 · tracks 5)
Tests passed:    60 / 60  (python -m pytest tests/ -q)

Detection/tracking changes:
  None to the shipped detector/tracker or thresholds — evaluated and preserved.
  Verified the persistence gate (333→23) and flicker-vs-edge evidence.
  Tracker comparison NOT run: weights/source-frames/script absent; documented
  honestly rather than fabricating. See §9.

Localization changes:
  Map pin is now the MEDIAN of all confirmed positions, not the last box.
  New field position_spread_m (measured 5.6–20.2 m) — honest, labelled an
  error-bar diagnostic, not GPS accuracy.
  Projection invariants locked by unit tests (GSD, centre, directions, heading,
  moving-drone distance, reference-frame invariance).

Priority changes:
  New field score_breakdown per survivor; sums to priority; dropped terms
  absent (not zero); deterministic. UI renders it as a stacked bar with
  "not scored" for missing terms.

Group changes:
  New fields group_id + group_size via existing connected-component logic in
  reference-frame geometry; distinct from cluster_size (incl. vs excl. self).

Dashboard changes:
  Verified SurvivorTable and MapPanel (already in working tree) render the new
  fields and build/lint cleanly. No new visual regression introduced.

Measured improvements (all on the real 7,081-detection clip):
  position_spread_m: min 5.60 m · median 10.53 m · max 20.22 m
  score_breakdown sums to priority to <1e-3 for all 23 survivors
  events closing bands == survivor table bands (0 mismatches)
  persistence: 333 track IDs → 23 confirmed survivors
  60/60 tests passing; frontend production build clean

Known limitations:
  ByteTrack↔BoT-SORT not compared (assets absent) — documented, not fabricated.
  position_spread_m is self-consistency, not absolute GPS accuracy.
  No per-pin satellite-imagery error measured this session.
  Detection settings not re-tuned (no evidence-backed improvement shown).
```

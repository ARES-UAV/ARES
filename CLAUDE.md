# ARES — Repository Context

## What this project is

An AI-assisted UAV system for disaster-zone search and rescue. Onboard vision detects survivors in drone imagery, tracks them without double-counting, localizes them on a map, ranks them by rescue priority, and surfaces it all on a command dashboard. The longer-term research contribution is **adaptive, risk-aware search planning** — choosing where to search next rather than flying a fixed grid.

This repo is a monorepo covering perception, planning, experiments and the dashboard.

## Hard deadline

**5 September 2026** — internal hackathon, the selection cutoff for Smart India Hackathon 2026 (Hardware Edition). **20 September** follows for the national submission.

Every decision trades in favour of **working on demo day** over impressive-but-fragile. If a feature could fail live on stage, it does not go in.

---

## Repository layout

```
ARES/
├── CLAUDE.md              # this file
├── README.md
├── requirements.txt       # backend only — light, no torch
├── docs/                  # research + technical documentation
├── ai/                    # perception: detection, tracking, export
│   └── requirements.txt   # ML deps — heavy, install separately
├── planning/              # search + adaptive planning algorithms
├── simulation/            # disaster / UAV simulation
├── experiments/           # evaluation results, one dir per experiment
│   ├── MODEL_SELECTION.md # ← read before touching model choice
│   └── Perception/C2A/    # YOLOv8n + YOLOv8s baselines and fine-tunes
├── hardware/              # UAV hardware and CAD
├── backend/               # FastAPI — dashboard API   (to be built)
└── frontend/              # Vite + React + Tailwind   (to be built)
```

`ai/`, `planning/`, `simulation/` and `hardware/` are currently README-only placeholders.

---

## The data contract — read before writing any code

All perception output crosses module boundaries as a JSON array of detection records. This format is agreed across the team and **must not be changed unilaterally**:

```json
{
  "frame_id": 0,
  "bbox": [x1, y1, x2, y2],
  "confidence": 0.87,
  "track_id": 2,
  "class": 0
}
```

- `frame_id` — zero-indexed frame number in the source video
- `bbox` — pixel coordinates, top-left and bottom-right, in the original frame's resolution
- `confidence` — 0.0 to 1.0
- `track_id` — persistent per-person ID across frames. `-1` means untracked. **The count of unique `track_id` values is the de-duplicated survivor count** — this is the number that matters, not the raw detection count.
- `class` — always `0` (person) for now. Hazard classes arrive in Phase 2.

Derived fields the backend adds (latitude, longitude, priority score) are computed server-side and are **not** part of this input contract.

---

## Detection model status (23 Aug 2026)

Current: **YOLOv12s**, single `person` class, trained on combined C2A + VisDrone. Epoch 44 of 100 — P 0.845, R 0.717, mAP50 0.775, mAP50-95 0.494. Interim weights: `ares_detect_v0.9.pt`.

- Operating confidence threshold: **0.18, deliberately low.** Recall at that threshold is **0.831** against 0.740 at the 0.5 default — 91 more survivors found per thousand. Surface on the dashboard as **"Detection Mode: High Recall"**.
- `max_det` must be **1000**, not the default 300.
- **`DETECTION_IMGSZ = 960`.** Detection runs on a 1280-wide clip; at 640 a 24 px person is downscaled to 12 px before the network sees them, and detections stop being stable. 960 gave +29% detections and doubled the share above 0.70 confidence. **The on-device benchmark must target 960, not 640** — the shipped detections were produced at that size.
- **Persistence is a duration, not a frame count.** `MIN_TRACK_SECONDS = 2.5`, with `MIN_TRACK_FRAMES = int(MIN_TRACK_SECONDS * CLIP_FPS)` — 60 frames at 24 fps, 3 at the Pi's ~1.5 fps. A hardcoded frame count silently means an eighth of a second in one place and two seconds in the other.
- **Maximum operating altitude ~40 m**, predicted from geometry and confirmed on real footage: above it a person spans under 24 px and detection quality collapses (4% of detections above 0.70 confidence, versus 32% on lower-altitude footage).
- On-device target: **Raspberry Pi 4 Model B**, CPU only. Expect a low FPS figure and display it honestly.

**Before changing model architecture, read `experiments/MODEL_SELECTION.md`.** This repo already contains trained YOLOv8n and YOLOv8s models whose relationship to YOLOv12s is not yet established — they were measured on a different test split.

---

## Demo footage policy — important

There is no physical drone. Demo footage comes from **public UAV datasets** (VisDrone-VID sequences, UAV123, or free stock aerial clips), and detections are produced by **running the real trained model over that footage**. The detections are genuine model output; only the flight is borrowed.

**Never hand-author or fabricate detection records for a demo.** If a judge asks "is this your model's output?", the answer has to be yes. A borrowed clip with real detections is honest and normal for a prototype. Invented bounding boxes are not, and one question would expose them.

`backend/data/fixture_detections.json` (generated by `tools/make_fixture.py`) exists **only** so the frontend can be built before real footage is processed. It is development scaffolding. It must never appear in a demo, a screenshot, or the recorded video. Delete it once real detections exist.

Drone GPS origin, altitude and FOV are assumed constants per clip. That assumption is disclosed in the pitch, not hidden.

---

## Demo-day constraints (non-negotiable)

1. **The demo replays a pre-computed detections file. It does not run inference live.** The backend streams stored events against a playback clock. Identical to a judge, and it removes every live-inference failure mode.
2. **The dashboard must work with the backend switched off.** Keep a path where the frontend loads a static JSON file directly.
3. **Map tiles need internet, and venue wifi fails.** Cache tiles for the demo area or fall back to a static georeferenced image. Do not discover this on 5 September.
4. **No API keys.** OpenStreetMap tiles via Leaflet need none.

---

## Localization — pixel to GPS

Nadir-pointing camera, known altitude `H`, flat local terrain. `H`, FOV and `(lat0, lon0)` are **fixed constants per demo clip** — there is no live telemetry in the prototype.

```
GSD      = 2 * H * tan(FOV / 2) / image_width    # metres per pixel

# Image y grows DOWNWARD. Latitude grows NORTHWARD. The subtraction reverses.
east_m   = (px - image_width  / 2) * GSD
north_m  = (image_height / 2 - py) * GSD         # <- note the reversed order

dlat     = north_m / 111320
dlon     = east_m  / (111320 * cos(lat0))
lat, lon = lat0 + dlat, lon0 + dlon
```

**Get the `north_m` sign wrong and every survivor mirrors across the drone position** — plausible-looking, entirely wrong, and invisible until someone checks a known point. Verify with the corners: a pixel in the **top-left** of the frame must come out **north and west** of the origin; **bottom-right** must come out **south and east**.

Use the **centre** of the bbox, not its bottom edge. Under a nadir camera the person is directly beneath their box centre; the bottom-edge convention only applies to oblique views.

Keep these constants in one config module, not scattered through the code.

At 640 px input with a 60° FOV, a 1.7 m person spans ~47 px at 20 m altitude and ~24 px at 40 m. **State a maximum operating altitude of roughly 40 m** rather than implying it works at any height.

---

## Priority scoring

Ranks survivors for rescue order. Keep it **simple and explainable** — a judge will ask how it works and "a neural network decides" is a bad answer. A weighted average of three normalised 0–1 terms: detection confidence, cluster size (survivors within `CLUSTER_RADIUS_M`), and hazard proximity. Weights, radius and thresholds all live in the config module; `priority.py` holds arithmetic and no numbers.

**Bands are an ordinal ramp, not four statuses** — quarters of the 0–1 range:

| Band | Score |
|---|---|
| Low | below 0.25 |
| Medium | 0.25 and above |
| High | 0.50 and above |
| Critical | 0.75 and above |

There is deliberately **no "clear" band and nothing green in the ramp** — every row is someone who still needs reaching.

**When `HAZARDS` is empty, the hazard term is dropped and the remaining weights renormalise.** It is never scored zero. Zero would read as "checked, nothing nearby" and would depress every score by the hazard weight; dropping it reads as "not measured", which is the truth. The dashboard says so on screen. Hazard classification is Phase 2 — do not populate `HAZARDS` with invented entries to make the ranking look livelier.

---

## Dashboard build state (24 Aug 2026)

Stages 0–5 complete. Running at `localhost:5173` against `localhost:8000`.

**Built and verified:** detection feed with bbox overlay on a shared playback clock · survivor map with moving-origin localization · reconciled stat header · survivor priority queue with the four-band ramp · mission event log · assumed-parameters panel · offline map tiles served locally · validated palette with self-hosted fonts.

**Endpoints:** `/api/detections` · `/api/survivors` · `/api/config` · `/api/events` · `/api/health` · `/tiles/{z}/{x}/{y}.png`

**Key invariants — do not break these:**

- Every count on screen derives from **one** `survivorsFound` array. The header renders its `.length`, the queue renders its rows, the map plots its members. There is no second tally anywhere, so the three cannot disagree.
- **The header shows three counts, and the gap between them is the point.** Raw detections this frame · unique track IDs so far · confirmed survivors. The gap between the last two is the price of the high-recall threshold — flicker and ID switches — and persistence filtering is what removes it. Showing all three is a stronger answer than hiding the difference.
- The event log's closing bands equal `/api/survivors` by construction — the final sample is forced. Asserted, not assumed.
- Priority is re-assessed at `EVENT_SAMPLE_INTERVAL_S`, not per frame. Per-frame scoring emits ~277 band changes on detector confidence noise alone. The sampling rate is stated in the panel footer; it is a disclosed design decision, not a fudge factor.
- Scores print at three decimals in the log and two in the table. Deliberate: 0.7499 rounds to "0.75" at two decimals and would read as contradicting a legend saying critical begins at 0.75.
- Map scroll-wheel zoom is **disabled**. The page scrolls, Leaflet eats wheel events over the panel, and one tick moved the map 196 m off the survivors mid-session. Buttons and drag-pan still work.

**Still outstanding:** static-mode bundle (waits on final data shape) · real detections replacing the fixture · Pi 4 FPS benchmark · Robin's persistence filter, `score_breakdown` and `position_spread_m`.

**Panels that must never be built:** battery, GPS signal, telemetry link, packet loss, storage, flight mode, weather, and any mission-control action button. There is no aircraft — every one of those would be a typed number presented as sensed. See `DASHBOARD_SPEC_TRIAGE.md`.

---

## Dashboard requirements

From a design review; not optional.

- **Counts must reconcile across every section.** Header saying 12 while the table shows 5 was the first mockup's biggest flaw. Derive every count from one shared state.
- **Show the de-duplicated tracked count next to the raw detection count.** Two numbers, both labelled.
- **Survivor cyan is a mark colour only** — boxes, pins, selection gutters. Never text, never a priority band. When a survivor line needs cyan, use a left gutter stripe, not coloured type.
- **RGB and thermal views must look genuinely different**, not the same image filtered.
- **Display the measured on-device FPS** and the **"Detection Mode: High Recall"** indicator on screen.
- **Make priority planning visible on the map** — annotate routes and reroutes rather than claiming adaptivity in text.
- Keep the mission date current. A stale placeholder date reads as unfinished.

---

## Scope — what is real and what is described

The pitch is deliberately honest about this split. **Do not build, mock, or imply the "described only" items.**

| Capability | Status |
|---|---|
| On-device AI inference | Built |
| Emergency alerting / priority scoring | Built |
| Command centre dashboard | In progress |
| Geo-tagged mapping | Built |
| Offline resilience | Built — a consequence of on-device inference |
| Multi-sensor fusion (RGB + thermal) | Partial — public thermal datasets, not hardware |
| Hazard classification | Partial — 3 of 7 classes (fire/smoke, flood, collapse), Phase 2 |
| Adaptive search planning | Research direction — simulation only, not flown |
| Autonomous navigation, GPS-denied SLAM | **Described only** — architecture write-up, not built |

---

## Team

| Person | Owns |
|---|---|
| **Dewang** | Detection model, hazard classifier, on-device benchmark. **All of backend and frontend.** |
| **Robin** | Tracking, pixel→GPS localization, priority scoring logic |
| **Ujjaini** | Pitch deck, presentation, demo video recording |

Ujjaini works from the finished dashboard to record the demo video — this repo is an input to her deliverables rather than one she contributes code to, so implementation tasks should not be assigned to her.

Robin owns `localize.py` and `priority.py`. If his versions are not ready, stub them from the formulas above and swap his in later — do not block the dashboard.

If a change touches the JSON contract, it affects all three. Flag it rather than changing it.

---

## Conventions

- **Backend work runs inside the project venv**: `source .venv/bin/activate` before invoking Python or uvicorn. Without it `fastapi` is not importable and endpoints cannot be exercised — code gets written but never actually run.
- Python: type hints on function signatures; Pydantic models for anything crossing an API boundary.
- Keep tunable constants (altitude, FOV, origin coordinates, drone speed and heading, threshold, scoring weights, sampling intervals) in `backend/config.py` and serve them at `/api/config`. Judges ask to see these, and the panel that displays them reads from that endpoint so it cannot drift.
- **Colour comes from `frontend/src/tokens.css` and nowhere else.** No raw hex outside that file. The palette was validated computationally for colourblind separation — substituting a value by eye can silently reintroduce a failure. Canvas and Leaflet cannot resolve `var()`, so `theme.js` reads computed values off `:root` for those two.
- **No gradients.** Flat surfaces only. A blue-to-dark gradient background is the most recognisable generative-AI tell and nothing in the token file produces one.
- **Every video asset gets `-movflags +faststart`.** Without it the browser downloads the whole file before it can report duration — 15 seconds of "Loading clip…" before controls enable.
- **Never commit model weights, datasets, or video.** Weights go to GitHub Releases. See `.gitignore`.
- Every experiment records: config, dataset version, model version, parameters, results, conclusion — and **the test split it was measured on**, which is how the current YOLOv8-vs-YOLOv12 ambiguity arose.
- Prefer boring, working solutions. This codebase is judged on 5 September.
- **Never commit secrets** — API keys, tokens, credentials, private endpoints. This file is public; treat everything in it as readable by anyone.

---

## Naming consistency

Two expansions of "ARES" are currently in use across the project's materials:

- **Adaptive Rescue and Exploration System** — `README.md`, `docs/project_overview.md`
- **Autonomous Rescue & Environmental Intelligence System** — pitch deck and planning material

The first reflects the research contribution (adaptive search planning); the second reflects the SIH framing. **One should be adopted everywhere before 5 September.** Until that decision is made, use the `README.md` form in anything written here rather than introducing a third variant.

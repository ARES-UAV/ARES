# ARES — Repository Conventions

## What this project is

An AI-assisted UAV system for disaster-zone search and rescue. Onboard vision detects survivors in drone imagery, tracks them without double-counting, localizes them on a map, ranks them by rescue priority, and surfaces it all on a command dashboard. The longer-term research contribution is **adaptive, risk-aware search planning** — choosing where to search next rather than flying a fixed grid.

This repo is a monorepo covering perception, planning, experiments and the dashboard.

## Hard deadline

**10 September 2026** — internal hackathon, the selection cutoff for Smart India Hackathon 2026 (Hardware Edition). Moved from 5 September; confirmed 31 August.

**~30 September** — national submission. **Estimated from last year's schedule, not confirmed by SIH.** It is a planning assumption; anything scheduled against it inherits that uncertainty. Confirm with the SPOC and correct this line.

Every decision trades in favour of **working on demo day** over impressive-but-fragile. If a feature could fail live on stage, it does not go in.

---

## Repository layout

```
ARES/
├── CONVENTIONS.md              # this file
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

## Detection model status (26 Aug 2026)

Current: **YOLOv12s**, single class, trained on combined C2A + VisDrone. Shipped weights: `models/yolov12s.pt` (9,231,267 params).

**Validated on the combined C2A + VisDrone val split — 2,591 images, 86,092 instances.** Same checkpoint at both sizes:

| | 640 | **960 (shipped)** |
|---|---|---|
| Precision | 0.854 | **0.864** |
| Recall | 0.727 | **0.774** |
| mAP50 | 0.783 | **0.833** |
| mAP50-95 | 0.511 | **0.577** |

The checkpoint records `epoch: 58` of a planned 100 (zero-indexed — 59 epochs completed). Earlier docs said epoch 44 with weaker numbers; that was a superseded checkpoint and the claim has been corrected everywhere.

- Operating confidence threshold: **0.18, deliberately low** — chosen off the PR curve, not from a default. Measured at 960:

  | | conf 0.37 (F1-optimal) | **conf 0.18 (shipped)** |
  |---|---|---|
  | Precision | 0.864 | 0.752 |
  | Recall | 0.775 | **0.824** |
  | F1 | 0.817 | 0.786 |

  Over 86,092 instances that is **+4,219 people found for +12,893 false alarms — about 3 false alarms per additional survivor.** Surface on the dashboard as **"Detection Mode: High Recall"**.
- `max_det` must be **1000**, not the default 300.
- **`DETECTION_IMGSZ = 960`.** Detection runs on a 1280-wide clip; at 640 a 24 px person is downscaled to 12 px before the network sees them, and detections stop being stable. 960 gave +29% detections and doubled the share above 0.70 confidence. **The on-device benchmark must target 960, not 640** — the shipped detections were produced at that size.
- **Persistence is a duration, not a frame count.** `MIN_TRACK_SECONDS = 2.5`, with `MIN_TRACK_FRAMES = int(MIN_TRACK_SECONDS * CLIP_FPS)` — 60 frames at 24 fps, 3 at the Pi's ~1.5 fps. A hardcoded frame count silently means an eighth of a second in one place and two seconds in the other.
- **Maximum operating altitude ~40 m**, predicted from geometry and confirmed on real footage: above it a person spans under 24 px and detection quality collapses (4% of detections above 0.70 confidence, versus 32% on lower-altitude footage).
- **On-device: measured on Qualcomm AI Hub, real hosted silicon.** INT8, `qnn_context_binary`:

  | | RB3 Gen 2 (QCS6490) | IQ-9075 EVK (QCS9075) |
  |---|---|---|
  | **960** | 209.50 ms · **4.8 FPS** | 62.30 ms · **16.1 FPS** |
  | 640 | 28.40 ms · 35.2 FPS | 14.04 ms · 71.2 FPS |
  | Peak memory | 3–7 / 3–6 MB | 2–6 / 6.5 MB |
  | **NPU coverage** | **489/489 — 100 %** | **489/489 — 100 %** |

  **All latencies are MEDIANS of ~100 samples.** AI Hub's
  `estimated_inference_time`, and the "Minimum Inference Time" headline on its
  console, is the fastest run of the hundred — and this repo published exactly
  that for a fortnight, overstating the IQ-9075 at 640 by 34 %. The shipped RB3
  figure survived because at 200 ms per inference the min/median gap is under
  1 %. Read the label on the field before you print it.

  The 100 % is the headline, not the FPS: every layer of an attention-centric YOLOv12 runs on the Hexagon NPU with nothing falling back to CPU.

- **The count does not survive device rate — measured 31 August.** Latency says 4.8 FPS
  on the RB3. Feeding the tracker every 5th frame to match that rate, confirmed survivors fall
  from **21 to 10**, and detections per frame fall 22.6 → 8.8 *on the same frames*. The detector is
  stateless, so that second number can only mean the tracker is discarding them: `model.track()`
  returns what ByteTrack accepted, and its low-score association stage keeps weak boxes only when
  they match an existing track. At 5× the frame gap they don't. Our conf-0.18 operating point
  depends on exactly those boxes.

  **BoT-SORT with GMC is the only config that finds the people** — 20 of 21 at 4.8 FPS — but it
  splits identities (one person into five) and reports 47. Tuned ByteTrack reports 20 against a
  true 21 *by missing 8 and double-counting 5*; the errors cancel into a plausible number. **Do
  not adopt that config on the strength of its count.** Finding is solved at device rate;
  counting is not. Full method and the per-tracker breakdown: `experiments/FRAME_RATE_STUDY.md`.

  The demo is unaffected — it replays a 24 FPS `detections.json`, as § Demo-day constraints
  requires. What this bounds is the *claim*, not the demonstration.

- **Raspberry Pi 4 is still unmeasured.** `DEVICE_FPS = None` renders "not yet measured". Qualcomm figures do not fill a Pi row.
- **INT8 accuracy is unmeasured.** All device latencies are INT8; all accuracy figures above are FP32. Never present them as one system.

**Before changing model architecture, read `experiments/MODEL_SELECTION.md` and `experiments/MODEL_COMPARISON_V8S_V12S.md`.**

*Updated 18 Sept 2026.* The YOLOv8s ↔ YOLOv12s relationship is **no longer open** — it was settled on a controlled comparison (same combined C2A + VisDrone validation split, `imgsz=960`, default `max_det`, epoch-matched). **YOLOv8s wins on every headline metric**: recall 0.8264 vs 0.8234, precision 0.8445 vs 0.8217, mAP50 0.8453 vs 0.8330 — 263 more true positives and 2,273 fewer false positives.

**The shipped model is still YOLOv12s.** Accuracy was only ever half the question; the swap is gated on device latency against v12s's measured 209.5 ms on the RB3, and that benchmark is still running. The decision rule was pre-registered before the numbers arrived: **faster than 209.5 ms → swap; slower → keep v12s.** Do not pre-empt it in any document.

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
3. **Map tiles need internet, and venue wifi fails.** Cache tiles for the demo area or fall back to a static georeferenced image. Do not discover this on 10 September.
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

**"On-device inference: Built" is about latency, not counting.** 4.8 FPS on the RB3 is measured
and holds. The de-duplicated survivor count at that rate does **not** — see the frame-rate entry
under Detection model status, and `experiments/FRAME_RATE_STUDY.md`. Say *"runs on device at
4.8 FPS"*; do not say *"produces the same survivor count on device"*.

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
- Prefer boring, working solutions. This codebase is judged on 10 September.
- **Never commit secrets** — API keys, tokens, credentials, private endpoints. This file is public; treat everything in it as readable by anyone.

---

## Naming consistency

Two expansions of "ARES" are currently in use across the project's materials:

- **Autonomous Rescue & Environmental Intelligence System** — everywhere. Settled
  29 September 2026. `README.md` and `docs/project_overview.md` used to say
  *Adaptive Rescue and Exploration System*; the site, the field manual, the deck
  and the planning material all said the other one, so the two outliers were
  changed rather than the six. If you are adding a new document, this is the
  expansion.

The first reflects the research contribution (adaptive search planning); the second reflects the SIH framing. **One should be adopted everywhere before 10 September.** Until that decision is made, use the `README.md` form in anything written here rather than introducing a third variant.

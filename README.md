# ARES
### Adaptive Rescue and Exploration System

An AI-assisted UAV system for disaster-zone search, survivor detection, and localization.

ARES aims to improve UAV search-and-rescue efficiency by dynamically adapting its search strategy according to detected survivors, uncertainty, environmental risk, and remaining mission energy.

> **Project status:** Research and software prototyping. Detection, evaluation and the command dashboard are in active development; UAV integration is not yet built.

---

## Overview

During disaster response, rapidly locating survivors is critical. UAVs can search large areas quickly, but limited battery, uncertain survivor locations, obstacles and changing conditions make efficient search difficult.

Conventional UAV search systems rely on predefined patterns — grid, lawnmower, spiral. ARES investigates an alternative in which the UAV continuously updates its search strategy using information gathered during the mission.

The project combines UAV autonomy, computer vision, RGB and thermal perception, survivor detection and tracking, survivor localization, risk-aware prioritization, adaptive search planning, energy-aware mission planning, and ground-station monitoring.

---

## System Architecture

```
                     UAV
                      │
           ┌──────────┴──────────┐
      RGB Camera            Thermal Camera
           └──────────┬──────────┘
                      ↓
               AI Detection
                      ↓
                 Tracking
                      ↓
              Sensor Fusion
                      ↓
           Survivor Localization
                      ↓
              Risk Estimation
                      ↓
          Adaptive Search Planner
                      ↓
               UAV Navigation
                      ↓
               Ground Station
```

---

## Adaptive Search Strategy

Instead of following a fixed pattern, ARES continuously determines which region of the disaster area should be searched next. The planner considers survivor probability, detection confidence, search uncertainty, survivor priority, distance, estimated energy cost, previously searched regions, and remaining mission time.

The approach is evaluated against conventional strategies — grid/lawnmower, random, and nearest-target search — using survivors detected, time to first survivor, time to locate all survivors, search coverage, flight distance, estimated energy consumption, and localization accuracy.

---

## Current Results — Survivor Detection

Four detection experiments are complete. Full analysis in [`experiments/MODEL_SELECTION.md`](./experiments/MODEL_SELECTION.md).

All rows evaluated on the **same** C2A test split — 2,043 images, 72,523 instances — at `imgsz=640`, `max_det=1000`. Latency on a Tesla T4.

| Model | Trained on | Epochs | GFLOPs | P | R | mAP50 | mAP50-95 | ms/img |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| YOLOv8n | COCO (baseline) | — | 8.1 | 0.312 | 0.189 | 0.131 | 0.060 | — |
| YOLOv8n | C2A | 50 | 8.1 | 0.843 | 0.728 | 0.776 | 0.489 | **4.09** |
| YOLOv8s | COCO (baseline) | — | 28.6 | 0.335 | 0.242 | 0.173 | 0.085 | — |
| YOLOv8s | C2A | 50 | 28.4 | 0.861 | 0.764 | 0.814 | 0.545 | 8.84 |
| **YOLOv12s** | **C2A + VisDrone** | **60** | **23.2** | **0.869** | **0.790** | **0.834** | **0.572** | 12.84 |

**YOLOv12s is the deployed model** — best on every metric, and by the widest margin on recall, which is the one that matters when a missed survivor is the failure the system exists to prevent. It finds 790 of every 1,000 survivors against the next model's 764. It was also trained on the broader C2A + VisDrone combination and still wins on C2A's own test split, so the wider training data cost nothing on the narrower domain.

**YOLOv8n is the edge fallback** — 2.9× fewer FLOPs and 3.1× faster, still reaching 0.728 recall. If onboard hardware cannot sustain the heavier model, that swap is already trained and already measured.

**Key finding.** Domain-specific fine-tuning matters more than architecture: a COCO-pretrained YOLOv8n finds fewer than one survivor in five (recall 0.189); fine-tuned on disaster imagery the same network finds nearly three in four (0.728) — a **285% relative gain in recall from training data alone**.

**Stated caveat.** The YOLOv8 models trained for 50 epochs and YOLOv12s for 60. This is therefore not a controlled architecture comparison and is not presented as one — it establishes which model to ship, which was the question being asked. Full analysis in [`experiments/MODEL_SELECTION.md`](./experiments/MODEL_SELECTION.md).

### Detection threshold — and what it buys

The deployed model runs at **confidence 0.18**, deliberately below the 0.5 default. In search and rescue the costs are asymmetric: a false alarm costs a rescuer seconds, a missed survivor cannot be recovered.

The table above reports recall at the balanced best-F1 point, which is what makes models comparable. At the actual operating threshold the figure is higher:

| Threshold | Recall | Missed per 1,000 survivors |
|---|---:|---:|
| 0.50 — library default | 0.740 | 260 |
| **0.18 — ARES operating point** | **0.831** | **169** |

**Running at 0.18 rather than the default finds 91 more survivors per thousand.** The threshold also sits on a flat region of the recall curve — recall varies by only 0.028 across 0.10–0.25 — so the system is not sensitive to small changes in that choice.

The dashboard surfaces this as a **High Recall** detection mode rather than hiding it.

---

## Command Dashboard

A mission-replay console. It plays a clip alongside the detections recorded from it, localizes each survivor, ranks them, and logs what happened — every panel reading the same clock.

- **Detection feed** — video with bounding boxes and track IDs, driven by a shared playback clock
- **Survivor map** — Leaflet, positions from pixel→GPS, tiles served locally so it works with no network
- **Priority queue** — survivors ranked, with the scoring formula printed underneath
- **Mission event log** — acquisitions, cluster formation and priority escalations, every line derived from detections
- **Mission parameters** — every constant the system depends on, each tagged `assumed`, `derived`, `chosen` or `measured`

Two properties are enforced rather than checked. Every count on screen derives from a single survivor array, so the header, the queue and the map cannot disagree. And the event log's closing bands equal the survivor endpoint's by construction.

**The dashboard shows no UAV telemetry** — no battery, GPS fix, link quality, storage, flight mode or weather. There is no aircraft in this prototype, so any value in those fields would be invented rather than sensed. The parameters panel names them explicitly as absent and says why.

The demo replays a pre-computed detections file rather than running inference live. Identical to a viewer, and it removes every live-inference failure mode from the demonstration.

---

## Data Contract

All perception output crosses module boundaries as a JSON array of detection records. This format is fixed across the project — detection, tracking, localization, scoring and the dashboard all depend on it.

```json
{
  "frame_id": 0,
  "bbox": [x1, y1, x2, y2],
  "confidence": 0.87,
  "track_id": 2,
  "class": 0
}
```

| Field | Meaning |
|---|---|
| `frame_id` | Zero-indexed frame number in the source video |
| `bbox` | Pixel coordinates, top-left and bottom-right, in the source resolution |
| `confidence` | 0.0 – 1.0 |
| `track_id` | Persistent per-person ID across frames; `-1` means untracked |
| `class` | `0` = person. Hazard classes arrive in Phase 2 |

**The count of unique `track_id` values is the de-duplicated survivor count** — the figure that matters operationally, as opposed to the raw detection count which counts the same person once per frame. Both are displayed, separately labelled.

Latitude, longitude and priority score are derived server-side and are not part of this input contract.

---

## Survivor Localization

Pixel coordinates are converted to GPS assuming a nadir-pointing camera at known altitude over locally flat terrain:

```
GSD     = 2 · H · tan(FOV / 2) / image_width     # metres per pixel

# Image y grows downward; latitude grows northward — the subtraction reverses
east_m  = (px - image_width  / 2) · GSD
north_m = (image_height / 2 - py) · GSD

Δlat    = north_m / 111320
Δlon    = east_m  / (111320 · cos(lat0))
```

Position is taken from the **centre** of each bounding box — under a nadir camera the subject lies directly beneath it. Sign convention is verified against frame corners: a top-left pixel resolves north-and-west of the origin, bottom-right south-and-east.

Altitude, FOV and origin coordinates are fixed constants per clip in the current prototype — there is no live telemetry yet. This assumption is stated rather than hidden.

At 640 px input with a 60° field of view, a 1.7 m person spans roughly 47 px at 20 m altitude and 24 px at 40 m, which sets a practical **maximum operating altitude of about 40 m** for reliable detection at this input resolution.

---

## Scope — Built vs Described

ARES is deliberately explicit about which capabilities are implemented and which are architectural proposals. Nothing in the "described" column is mocked or presented as working.

| Capability | Status |
|---|---|
| On-device AI inference | Built |
| Emergency alerting / priority scoring | Built |
| Command centre dashboard | Built |
| Geo-tagged mapping | Built |
| Offline resilience | Built — a consequence of on-device inference |
| Multi-sensor fusion (RGB + thermal) | Partial — public thermal datasets, not physical hardware |
| Hazard classification | Partial — 3 of 7 classes (fire/smoke, flood, collapsed structures) |
| Adaptive search planning | Research direction — simulation only, not flown |
| Autonomous navigation, GPS-denied SLAM | Described only — architecture write-up, not built |

Detection results are produced by running the trained model over public UAV datasets (C2A, VisDrone). There is no physical drone in the current prototype; demo footage is borrowed, but every detection shown is genuine model output.

---

## Repository Structure

```
ARES/
├── docs/                   Research and technical documentation
│   ├── project_overview.md
│   ├── research_problem.md
│   └── roadmap.md
├── ai/                     Perception: detection, tracking, export
│   └── requirements.txt    ML dependencies (heavy — install separately)
├── planning/               Search and adaptive planning algorithms
├── simulation/             Disaster and UAV simulation
├── experiments/            Evaluation results, one directory per experiment
│   ├── MODEL_SELECTION.md  Detection model comparison and analysis
│   └── Perception/C2A/     YOLOv8n and YOLOv8s baselines and fine-tunes
├── hardware/               UAV hardware and CAD
├── backend/                FastAPI dashboard API
├── frontend/               Vite + React command dashboard
├── tools/                  Development utilities
├── CLAUDE.md               Working context and project conventions
├── BUILD_ORDER.md          Dashboard implementation sequence
└── requirements.txt        Backend dependencies (light — no ML stack)
```

`ai/`, `planning/`, `simulation/` and `hardware/` currently hold documentation only.

---

## Getting Started

Dependencies are split so the dashboard does not pull in the ML stack.

```bash
# Dashboard backend — FastAPI, uvicorn, pydantic
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Perception — ultralytics, torch, onnx. Only needed for training,
# validation, export or benchmarking.
pip install -r ai/requirements.txt
```

Datasets and model weights are not stored in this repository. Trained weights are published as release assets.

---

## Roadmap

**Research and software** — problem definition · literature review · dataset preparation · human detection · object tracking · survivor localization · search simulation · adaptive search algorithm

**UAV integration** — hardware selection · assembly · telemetry · camera integration · waypoint navigation · autonomous mission

**Research validation** — controlled experiments · baseline comparison · ablation study · results · publication

Detailed timeline in [`docs/roadmap.md`](./docs/roadmap.md).

---

## Team

ARES Research & Development Team — three members across perception, planning, and presentation.

| Track | Scope |
|---|---|
| Perception | Detection model, hazard classification, on-device benchmarking, dashboard |
| Pipeline | Tracking, pixel-to-GPS localization, priority scoring |
| Presentation | Technical documentation, pitch materials, demonstration |

---

## License

See [LICENSE](./LICENSE).

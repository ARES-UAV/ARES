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

| Model | Trained on | Evaluated on | P | R | mAP50 | mAP50-95 | ms/img |
|---|---|---|---:|---:|---:|---:|---:|
| YOLOv8n | COCO (baseline) | C2A test | 0.312 | 0.189 | 0.131 | 0.060 | — |
| YOLOv8n | C2A fine-tuned | C2A test | 0.843 | 0.728 | 0.774 | 0.488 | 4.4 |
| YOLOv8s | COCO (baseline) | C2A test | 0.335 | 0.242 | 0.173 | 0.085 | 8.2 |
| YOLOv8s | C2A fine-tuned | C2A test | **0.861** | **0.764** | **0.812** | **0.544** | 8.1 |
| YOLOv12s | C2A + VisDrone | *combined val* | 0.845 | 0.717 | 0.775 | 0.494 | in progress |

C2A test split: 2,043 images / 72,523 instances. Latency measured on a Tesla T4.

**Key finding.** Domain-specific fine-tuning is transformative: a COCO-pretrained YOLOv8n finds fewer than one survivor in five (recall 0.189); fine-tuned on disaster imagery it finds nearly three in four (0.728) — a 286% relative gain in recall from training data alone.

**Open comparison.** The YOLOv12s row was measured on a different, harder validation set that includes dense VisDrone urban scenes, so it is *not* directly comparable to the rows above it. Cross-evaluation on the common C2A split is pending before a final model is selected.

### Detection threshold

The deployed model runs at a deliberately low confidence threshold — **~0.18**, rather than the 0.5 default. In search and rescue the costs are asymmetric: a false alarm costs a rescuer seconds, a missed survivor cannot be recovered. The system is therefore tuned for recall over precision, and surfaces this as a **High Recall** detection mode rather than hiding it.

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
GSD    = 2 · H · tan(FOV / 2) / image_width     # metres per pixel
Δx, Δy = pixel_offset_from_centre · GSD          # metres
Δlat   = Δy / 111320
Δlon   = Δx / (111320 · cos(lat0))
```

Altitude, FOV and origin coordinates are fixed constants per clip in the current prototype — there is no live telemetry yet. This assumption is stated rather than hidden.

At 640 px input with a 60° field of view, a 1.7 m person spans roughly 47 px at 20 m altitude and 24 px at 40 m, which sets a practical **maximum operating altitude of about 40 m** for reliable detection at this input resolution.

---

## Scope — Built vs Described

ARES is deliberately explicit about which capabilities are implemented and which are architectural proposals. Nothing in the "described" column is mocked or presented as working.

| Capability | Status |
|---|---|
| On-device AI inference | Built |
| Emergency alerting / priority scoring | Built |
| Command centre dashboard | In progress |
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
├── backend/                FastAPI dashboard API          (in progress)
├── frontend/               Vite + React command dashboard  (in progress)
├── tools/                  Development utilities
├── CLAUDE.md               Working context and project conventions
├── BUILD_ORDER.md          Dashboard implementation sequence
└── requirements.txt        Backend dependencies (light — no ML stack)
```

`ai/`, `planning/`, `simulation/` and `hardware/` currently hold documentation only.

---

## Getting Started

Dependencies are split so the dashboard does not pull in the ML stack.
The dashboard is two processes — run each in its own terminal.

**Backend — FastAPI on port 8000**

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Frontend — Vite dev server on port 5173**

```bash
cd frontend && npm install
npm run dev
```

Check the backend is alive at <http://localhost:8000/api/health>; interactive API
docs are at <http://localhost:8000/docs>. The dashboard is at <http://localhost:5173>.

Perception dependencies are separate and only needed for training, validation,
export or benchmarking:

```bash
pip install -r ai/requirements.txt   # ultralytics, torch, onnx — heavy
```

Datasets and model weights are not stored in this repository. Trained weights are
published as release assets.

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
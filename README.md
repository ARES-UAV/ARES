# ARES
### Autonomous Rescue & Environmental Intelligence System

An AI-assisted UAV system for disaster-zone search, survivor detection, and localization.

ARES aims to improve UAV search-and-rescue efficiency by dynamically adapting its search strategy according to detected survivors, uncertainty, environmental risk, and remaining mission energy.

> **Project status:** Research and software prototyping. Detection, evaluation, on-device benchmarking and the command dashboard are complete and measured; UAV integration is not built.

---

## See it running

| | |
|---|---|
| **Live site** | <https://ares.paralux.in> |
| **Engineering handbook** | [`docs/handbook/`](./docs/handbook/) — thirteen parts, beginner to advanced |
| **Single source of truth for every number** | [`experiments/ARES_MEASURED_NUMBERS.md`](./experiments/ARES_MEASURED_NUMBERS.md) |

Four recordings. Each one shows the thing running, not slides about it.

| | Video | What it shows |
|---|---|---|
| 01 | [The case for ARES](https://youtu.be/J89oZT977GU) | The system end to end, and what we deliberately did not build |
| 02 | [The adaptive planner](https://youtu.be/nnc5-N-GEU4) | 100 simulated missions against a lawnmower grid, including the no-information control |
| 03 | [Detection to GPS](https://youtu.be/das3HfpK2vY) | 7,081 raw boxes becoming 23 located people |
| 04 | [The command dashboard](https://youtu.be/VloJFoPbxy4) | Live map, ranked rescue queue, alerts held offline |

---

## Headline results

Every figure below was measured. Nothing is estimated. What has *not* been measured is listed explicitly at the end of this section — see [`experiments/ARES_MEASURED_NUMBERS.md`](./experiments/ARES_MEASURED_NUMBERS.md) for the single source of truth.

**Detection accuracy** — YOLOv12s, single class, combined C2A + VisDrone validation split (2,591 images, 86,092 instances). Same checkpoint at both sizes:

| | 640 | **960 — deployed** |
|---|---:|---:|
| Precision | 0.854 | **0.864** |
| Recall | 0.727 | **0.774** |
| mAP50 | 0.783 | **0.833** |
| mAP50-95 | 0.511 | **0.577** |

For scale: stock YOLOv12s scores 48.0 mAP50-95 on COCO. **57.7 on small aerial humans**, from 9.2 M parameters.

**On-device** — Qualcomm AI Hub, real hosted silicon, INT8, `qnn_context_binary`:

| | Dragonwing RB3 Gen 2 | Dragonwing IQ-9075 EVK |
|---|---:|---:|
| **960 px** | 209.50 ms · **4.8 FPS** | 62.30 ms · **16.1 FPS** |
| 640 px | 28.40 ms · 35.2 FPS | 14.04 ms · 71.2 FPS |
| Peak memory | 3–7 / 3–6 MB | 2–6 / 6.5 MB |
| **Layers on Hexagon NPU** | **489 / 489 — 100 %** | **489 / 489 — 100 %** |

Latencies are **medians of ~100 samples**, not minimums — see
[`experiments/QUALCOMM_BENCHMARK.md`](./experiments/QUALCOMM_BENCHMARK.md).

**The 100 % is the headline, not the frame rate.** Every layer of an attention-centric YOLOv12 executes on the NPU with nothing falling back to CPU.

**Coverage** — at 20 m altitude the camera sees 23.09 m of ground; at 5 m/s the aircraft takes 4.6 s to cross its own footprint. At 4.8 FPS that is **~22 looks at every patch of ground**. Compute is not the binding constraint; per-look recall is.

**The adaptive planner — simulated, not flown.** This is the one headline figure on this page that is not a measurement of hardware, and it is labelled that way everywhere it appears. What *is* measured inside it is the detector: the simulation flies at our own P(detect) = 0.824, the recall measured at conf 0.18 and 960 px over 86,092 instances. Everything else — the aircraft, the terrain, the survivors — is synthetic. There is no aircraft.

Both planners fly identical worlds: same survivor layout, same detection coin-flips, same battery. The only thing that differs is where each one chooses to go next. Medians over 100 seeds:

| Prior quality | Planner | Found / 20 | Time to half | Ground covered |
|---|---|---:|---:|---:|
| good (r = 0.65) | lawnmower grid | 11.0 | 905 s | 55 % |
| good (r = 0.65) | **adaptive** | **20.0** | **291 s** | 33 % |
| none (r = −0.01) | lawnmower grid | 11.0 | 905 s | 55 % |
| none (r = −0.01) | **adaptive** | 11.0 | **715 s** | 48 % |

**Speed-up to half the survivors: 3.11× with a good prior, 2.10× with a mediocre one, 1.27× with none at all.**

The bottom two rows are the result worth reading. Given a probability map no better than chance, adaptive finds **no more people** than the grid — it just reaches half of them sooner, by learning in flight. The honest claim is therefore narrower than "it always wins", and [`simulation/RESULTS.md`](./simulation/RESULTS.md) states it that way, along with the two bugs the experiment caught and the 18 % the uniform figure fell when the run went from 30 seeds to 100.

Reproduce it in about six seconds:

```bash
python simulation/run.py           # 100 seeds, all three priors
python simulation/check_baseline.py   # confirms the grid baseline is information-blind
```

### Not measured

Stated as unmeasured everywhere they appear, because a table with no gaps invites the question of which entries were guessed.

| | Why it matters |
|---|---|
| **INT8 accuracy** | Every device latency above is INT8; every accuracy figure is FP32. They are two different models until measured. |
| **Raspberry Pi 4** | `DEVICE_FPS = None` renders "not yet measured". Qualcomm figures do not fill a Pi row. |
| **Power draw** | AI Hub reports latency, not watts. Duty cycle is a proxy. |

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

> **This table answers "which model do we ship?", not "how good is the shipped system?"** It holds split and resolution constant so the architectures are comparable. The deployed configuration runs at 960 px and is validated on the harder combined C2A + VisDrone split — those are the numbers in [Headline results](#headline-results) above, and they are lower here because the combined split contains dense VisDrone crowds that C2A does not.

| Model | Trained on | Epochs | GFLOPs | P | R | mAP50 | mAP50-95 | ms/img |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| YOLOv8n | COCO (baseline) | — | 8.1 | 0.312 | 0.189 | 0.131 | 0.060 | — |
| YOLOv8n | C2A | 50 | 8.1 | 0.843 | 0.728 | 0.776 | 0.489 | **4.09** |
| YOLOv8s | COCO (baseline) | — | 28.6 | 0.335 | 0.242 | 0.173 | 0.085 | — |
| YOLOv8s | C2A | 50 | 28.4 | 0.861 | 0.764 | 0.814 | 0.545 | 8.84 |
| **YOLOv12s** | **C2A + VisDrone** | **59** | **23.2** | **0.869** | **0.790** | **0.834** | **0.572** | 12.84 |

**YOLOv12s is the deployed model** — best on every metric, and by the widest margin on recall, which is the one that matters when a missed survivor is the failure the system exists to prevent. It finds 790 of every 1,000 survivors against the next model's 764. It was also trained on the broader C2A + VisDrone combination and still wins on C2A's own test split, so the wider training data cost nothing on the narrower domain.

**YOLOv8n is the edge fallback** — 2.9× fewer FLOPs and 3.1× faster, still reaching 0.728 recall. If onboard hardware cannot sustain the heavier model, that swap is already trained and already measured.

**Key finding.** Domain-specific fine-tuning matters more than architecture: a COCO-pretrained YOLOv8n finds fewer than one survivor in five (recall 0.189); fine-tuned on disaster imagery the same network finds nearly three in four (0.728) — a **285% relative gain in recall from training data alone**.

**Stated caveat.** The YOLOv8 models trained for 50 epochs and YOLOv12s for 59 (the shipped checkpoint records `epoch: 58`, zero-indexed). This table is therefore not a controlled architecture comparison and is not presented as one — it establishes which model to ship, which was the question being asked. Full analysis in [`experiments/MODEL_SELECTION.md`](./experiments/MODEL_SELECTION.md).

> **Superseded in part, 18 Sept 2026.** A controlled comparison has since been run — same combined validation split, `imgsz=960`, default `max_det`, epoch-matched — and **YOLOv8s beats YOLOv12s on every headline metric** (recall 0.8264 vs 0.8234, precision 0.8445 vs 0.8217, mAP50 0.8453 vs 0.8330). YOLOv12s remains the shipped model pending a device-latency benchmark; the swap rule was fixed in advance at *faster than 209.5 ms on the RB3 → swap.* See [`experiments/MODEL_COMPARISON_V8S_V12S.md`](./experiments/MODEL_COMPARISON_V8S_V12S.md).

### Detection threshold — and what it buys

The deployed model runs at **confidence 0.18**, deliberately below the 0.5 default. In search and rescue the costs are asymmetric: a false alarm costs a rescuer seconds, a missed survivor cannot be recovered.

Measured at 960 px on the combined validation split, read off the PR curve:

| Threshold | Precision | Recall | F1 | Missed per 1,000 |
|---|---:|---:|---:|---:|
| 0.37 — F1-optimal | 0.864 | 0.775 | **0.817** | 225 |
| **0.18 — ARES operating point** | 0.752 | **0.824** | 0.786 | **176** |

Over 86,092 instances that is **+4,219 people found for +12,893 false alarms — about 3 extra false alarms per additional survivor.**

The comparison is against the **F1 optimum**, not the 0.5 library default. Beating a default proves nothing; leaving the best-balanced point on purpose is the actual engineering decision, and 3:1 is a ratio a reviewer can evaluate immediately. An operator dismisses a false box in a second; a missed survivor is not recoverable.

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
│   ├── handbook/           13-part technical handbook, beginner to advanced
│   ├── index.html          The public site — served at ares.paralux.in
│   ├── img/                Screenshots used by the site
│   ├── ARES_ROBIN_GUIDE_v4.md     Integration guide for the pipeline owner
│   ├── PRIORITY_PRIOR_AND_OFFLINE.md
│   ├── project_overview.md
│   ├── research_problem.md
│   └── roadmap.md
├── simulation/             The adaptive-search experiment — code, design and results
│   ├── DESIGN.md           Written before the code, unchanged since
│   ├── RESULTS.md          100-seed experiment log, including the bugs it caught
│   ├── config.py           Every constant, each tagged assumed / derived / chosen / measured
│   ├── world.py            Survivor placement and prior generation
│   ├── planners.py         The lawnmower baseline and the adaptive planner
│   ├── run.py              The experiment runner
│   ├── check_baseline.py   Proves the baseline cannot use information
│   └── results/            Generated table, JSON and plot
├── backend/                FastAPI dashboard API
│   ├── localize.py         Pixel → GPS, and the error budget for the nadir assumption
│   ├── priority.py         The transparent rescue-priority score
│   ├── routing.py          A* over a risk-weighted cost grid
│   ├── alerts.py           Alert derivation and the delivery ledger
│   └── data/               The pre-computed demo detections and offline map tiles
├── frontend/               Vite + React command dashboard
├── experiments/            Evaluation results, one directory per experiment
│   ├── ARES_MEASURED_NUMBERS.md   Single source of truth for every figure
│   ├── QUALCOMM_BENCHMARK.md      On-device results from Qualcomm AI Hub
│   ├── MODEL_SELECTION.md         Detection model comparison and analysis
│   ├── MODEL_COMPARISON_V8S_V12S.md  The controlled re-run, and why we did not swap
│   └── Perception/C2A/            YOLOv8n and YOLOv8s baselines and fine-tunes
├── tools/                  Development utilities
│   ├── qualcomm_benchmark.py      Quantize → compile → profile on AI Hub
│   ├── fix_onnx_io.py             Repairs an Ultralytics ONNX spec violation
│   └── benchmark.py               Local latency measurement
├── planning/               Team plans and per-group scopes
├── pitch/                  SIH decks
├── ai/                     Perception notes
│   └── requirements.txt    ML dependencies (heavy — install separately)
├── hardware/               UAV hardware notes and the bill of materials
├── CONVENTIONS.md          Working context and project conventions
└── requirements.txt        Backend dependencies (light — no ML stack)
```

`ai/`, `planning/` and `hardware/` hold documentation only. `simulation/`, `backend/` and `frontend/` hold code that runs.

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

### Reproducing the numbers

```bash
# The adaptive-search experiment — no weights, no GPU, about six seconds
python simulation/run.py
python simulation/check_baseline.py

# Accuracy — combined C2A + VisDrone validation split
yolo val model=models/yolov12s.pt data=<combined>.yaml imgsz=960

# On-device — requires a free Qualcomm AI Hub token
python tools/fix_onnx_io.py models/yolov12s_960.onnx
python tools/qualcomm_benchmark.py --list
python tools/qualcomm_benchmark.py \
    --device "Dragonwing RB3 Gen 2 Vision Kit" --device-os 1.6 --quantize
```

Two things that will silently give you wrong answers, both of which bit this project:

- **`print(m.model.names)` before trusting any validation number.** A missing weights path makes Ultralytics download the stock COCO checkpoint and validate *that* — it reports plausible numbers for a model you did not train.
- **`imgsz` must match what you ship.** The benchmark reads the input size out of the ONNX graph rather than trusting a flag, because exports that were 640 when everyone believed they were 960 have already happened here once.

---

## Roadmap

**Research and software** — problem definition · literature review · dataset preparation · human detection · object tracking · survivor localization · search simulation · adaptive search algorithm

**UAV integration** — hardware selection · assembly · telemetry · camera integration · waypoint navigation · autonomous mission

**Research validation** — controlled experiments · baseline comparison · ablation study · results · publication

**Next measurements, in priority order**

1. **INT8 accuracy** — closes the only gap between the accuracy and latency tables
2. **Raspberry Pi 4** — commodity-hardware datapoint alongside the Qualcomm one
3. **YOLOv8n resolution scaling** — v8n is pure convolution, so benchmarking it at 640 and 960 would settle whether the RB3's 7.38× resolution penalty on the NPU is attention's quadratic term or a memory-tiling effect. The IQ-9075's 4.44× already sits inside attention's predicted band; the RB3's does not. Currently an open question, not a finding.

Detailed timeline in [`docs/roadmap.md`](./docs/roadmap.md).

---

## Team

ARES Research & Development Team — three members across perception, planning, and presentation.

| Track | Scope |
|---|---|
| Perception & platform | Detection model, hazard classifier, on-device benchmarking, backend and dashboard |
| Pipeline | Tracking, pixel-to-GPS localization, priority scoring |
| Presentation | Pitch deck, demonstration video |

---

## License

See [LICENSE](./LICENSE).

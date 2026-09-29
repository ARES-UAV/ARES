# AI

Perception: detection, tracking and export. The trained model is not in this
directory — weights are published as GitHub Release assets rather than
committed, because a 54 MB checkpoint in git history is carried by every clone
forever.

`requirements.txt` here is the heavy ML stack (ultralytics, torch, onnx). The
dashboard does not need it; install it only for training, validation, export or
benchmarking.

```bash
pip install -r ai/requirements.txt
```

## What is built

| | Status | Where the numbers are |
|---|---|---|
| Survivor detection, RGB | **Trained and validated.** YOLOv12s, single `person` class, combined C2A + VisDrone. Recall **0.824** at conf 0.18, 960 px, over 86,092 instances. | [`../experiments/MODEL_SELECTION.md`](../experiments/MODEL_SELECTION.md), [`../experiments/ARES_MEASURED_NUMBERS.md`](../experiments/ARES_MEASURED_NUMBERS.md) |
| Operating threshold | **Derived, not inherited.** 0.18 rather than the 0.5 default, chosen against the F1 optimum at a measured cost of ≈3 false alarms per additional person found. | [`../experiments/V8S_THRESHOLD.md`](../experiments/V8S_THRESHOLD.md) |
| Tracking / de-duplication | **Built.** ByteTrack. 7,081 raw detections over 320 frames become 333 track IDs and 23 people. | [`../docs/handbook/03_tracking.md`](../docs/handbook/03_tracking.md) |
| Export and on-device benchmark | **Measured on real silicon.** INT8 on a Dragonwing RB3 Gen 2: 209.5 ms at 960 px, **489 of 489 layers on the Hexagon NPU**. | [`../experiments/QUALCOMM_BENCHMARK.md`](../experiments/QUALCOMM_BENCHMARK.md) |
| Architecture comparison | **Run, and the result was not adopted.** A controlled re-run has YOLOv8s ahead of YOLOv12s on accuracy; the swap rule was fixed in advance and requires a device latency we have not measured, so v12s is still shipped. | [`../experiments/MODEL_COMPARISON_V8S_V12S.md`](../experiments/MODEL_COMPARISON_V8S_V12S.md) |

## What is partial

| | |
|---|---|
| **Thermal** | A separate YOLOv8s on HIT-UAV, recall 0.883. Demonstrated on public thermal imagery. We do not own a thermal camera. |
| **RGB + thermal fusion** | Late fusion, planned and specified, using the two models that exist. See [`../experiments/FUSION_PLAN.md`](../experiments/FUSION_PLAN.md) and [`../experiments/SENSOR_FUSION.md`](../experiments/SENSOR_FUSION.md). |
| **Hazard classification** | Not trained. `HAZARDS` is an empty list in the backend and the dashboard shows nothing rather than something invented. AIDER is the intended dataset. |

## What is not measured

Stated here because a table with no gaps invites the question of which entries
were guessed.

- **INT8 accuracy.** Every device latency is INT8; every accuracy figure is
  FP32. Until that is closed they describe two different models.
- **Power draw.** AI Hub reports latency, not watts.
- **Raspberry Pi 4.** `DEVICE_FPS = None`. The Qualcomm figures do not fill a
  Pi row and the dashboard renders "not yet measured" rather than a number.

## Datasets

C2A, VisDrone and HIT-UAV, all public. Not stored in this repository, and not
redistributed.

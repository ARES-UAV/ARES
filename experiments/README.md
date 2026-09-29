# Experiments

This directory contains reproducible experiments and evaluation
results for ARES.

## Completed Experiments

### AI Detection — YOLOv8n on C2A

A YOLOv8n COCO-pretrained baseline was evaluated on the C2A Human
Detection test set and compared with a YOLOv8n model fine-tuned on C2A.

- Test images: 2,043
- Test instances: 72,523

| Metric | YOLOv8n Baseline | YOLOv8n C2A Fine-tuned |
|---|---:|---:|
| Precision | 0.312 | **0.843** |
| Recall | 0.189 | **0.728** |
| mAP50 | 0.131 | **0.774** |
| mAP50-95 | 0.060 | **0.488** |
| Inference latency | — | **4.4 ms/image** |

The C2A fine-tuned model showed substantial improvement over the
COCO-pretrained baseline, particularly in mAP and recall.

### Current Finding

C2A-specific fine-tuning significantly improves YOLOv8n human
detection performance on the C2A test set.

The experiment provides the baseline for comparison with larger YOLO
models.

## What is in this directory

| File | Question it answers | Status |
|---|---|---|
| [`ARES_MEASURED_NUMBERS.md`](./ARES_MEASURED_NUMBERS.md) | **The single source of truth.** Every figure quoted in a deck, a video or on the site, with its provenance — and a list of what is *not* measured. | Live |
| [`MODEL_SELECTION.md`](./MODEL_SELECTION.md) | Which detection model do we ship? | Done |
| [`MODEL_COMPARISON_V8S_V12S.md`](./MODEL_COMPARISON_V8S_V12S.md) | A controlled, epoch-matched re-run of v8s against the shipped v12s. v8s wins on accuracy; the pre-registered swap rule needs a device latency we do not have, so nothing was swapped. | Done — result not adopted, and why |
| [`V8S_THRESHOLD.md`](./V8S_THRESHOLD.md) | Where should the confidence threshold sit? Re-derived rather than inherited; lands at 0.18 again. | Done |
| [`QUALCOMM_BENCHMARK.md`](./QUALCOMM_BENCHMARK.md) | How fast is it on real edge silicon? 209.5 ms at 960 px INT8 on a Dragonwing RB3 Gen 2, 489/489 layers on the NPU. | Done — on hosted hardware |
| [`V8S_BENCHMARK_RUNBOOK.md`](./V8S_BENCHMARK_RUNBOOK.md) | The procedure for the one measurement that would settle the model question. | **Runbook only — not run** |
| [`FRAME_RATE_STUDY.md`](./FRAME_RATE_STUDY.md) | Is 4.8 FPS enough to find people, and is it enough to count them? | Done |
| [`THERMAL_MODEL.md`](./THERMAL_MODEL.md) | Thermal detection on HIT-UAV. | Done |
| [`SENSOR_FUSION.md`](./SENSOR_FUSION.md), [`FUSION_PLAN.md`](./FUSION_PLAN.md) | How RGB and thermal combine. | Specified, not built |
| `Perception/C2A/` | The YOLOv8n and YOLOv8s training runs — validation batches, confusion matrices, PR curves. | Done |
| `qualcomm/`, `trackers/`, `frame_rate_*.json` | Raw outputs behind the files above. | — |

The adaptive-search experiment is not here. It lives in
[`../simulation/`](../simulation/) with its own design document and results,
because the code and the write-up belong together.

## Still open

Listed rather than dropped, because a plan that quietly loses its unfinished
items is not a plan.

| | Why it matters |
|---|---|
| **INT8 accuracy** | Every latency figure is INT8; every accuracy figure is FP32. Until this is closed they describe two different models. This is the highest-value remaining measurement. |
| **YOLOv8s on device** | The only axis left in the model question. `V8S_BENCHMARK_RUNBOOK.md` is the procedure; the decision rule was written before the measurement. |
| **Raspberry Pi 4** | A commodity-hardware datapoint alongside the Qualcomm one. `DEVICE_FPS` is `None` until then. |
| **Power draw** | AI Hub reports latency, not watts. |
| **Hazard classification** | Not trained. `HAZARDS` is empty and the dashboard shows nothing rather than something invented. |
| **Localization error against ground truth** | The pixel→GPS projection is derived and its error budget is written down, but it has never been checked against surveyed positions. |
| **Random-search and nearest-target baselines** | The planner chart has two lines. A third and fourth control were in the original plan. |

## Experiment policy

Every experiment here records: configuration, dataset and version, model and
version, parameters, number of trials, results, conclusions — and, where the
result contradicted what was expected, that too. `MODEL_COMPARISON_V8S_V12S.md`
and `../simulation/RESULTS.md` both exist largely because of that last clause.

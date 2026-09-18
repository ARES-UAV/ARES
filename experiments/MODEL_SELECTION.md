# Model Selection — Survivor Detection

*Last updated 23 Aug 2026 · owner: Dewang*


> ### ⚠ Partly superseded — read this first (18 Sept 2026)
>
> This document is kept because it records how the model decision was actually
> made. Three of its conclusions have since been overtaken by measurement:
>
> 1. **The "two-model story" is dead.** This file proposes YOLOv8n onboard and
>    YOLOv12s as *"the ground-station model, re-runs the footage once it
>    lands."* ARES no longer has a ground-station model. **Everything that
>    decides anything runs on the aircraft** — the ground station receives
>    survivor records and draws the map. Do not pitch the two-tier split.
> 2. **The target device is not a Raspberry Pi 4.** It is a Qualcomm Dragonwing
>    RB3 Gen 2 (QCS6490), and the benchmark has been run: YOLOv12s INT8 at
>    960 px is **209.5 ms / 4.8 FPS** on the NPU. The "benchmark plan" table
>    below was never filled in on a Pi and will not be. See
>    `ARES_MEASURED_NUMBERS.md`.
> 3. **No fallback to YOLOv8n was needed.** v12s clears a usable rate on the
>    real device.
>
> The architecture ranking here was also measured at 640 px on the C2A-only
> split. The controlled comparison at the deployed 960 px on the combined split
> is in **`MODEL_COMPARISON_V8S_V12S.md`**, and it reverses the result:
> **YOLOv8s beats YOLOv12s on every headline metric.** v12s remains shipped
> pending a device-latency benchmark.

---

This repository already contains four completed detection experiments. This document pulls them into one place, states what they do and do not prove, and names the single comparison that is still missing.

---

## Results so far

All YOLOv8 rows were evaluated on the **C2A test split**: 2,043 images, 72,523 instances.

| Model | Trained on | Params | GFLOPs | P | R | mAP50 | mAP50-95 | ms/img (T4) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| YOLOv8n | COCO only (baseline) | 3.01 M | 8.1 | 0.312 | 0.189 | 0.131 | 0.060 | — |
| YOLOv8n | C2A fine-tuned | 3.01 M | 8.1 | 0.843 | 0.728 | 0.774 | 0.488 | **4.4** |
| YOLOv8s | COCO only (baseline) | 11.16 M | 28.6 | 0.335 | 0.242 | 0.173 | 0.085 | 8.2 |
| YOLOv8s | C2A fine-tuned | 11.13 M | 28.4 | **0.861** | **0.764** | **0.812** | **0.544** | 8.1 |
| YOLOv12s @ 640 | C2A + VisDrone combined | 9.23 M | 23.2 | 0.854 | 0.727 | 0.783 | 0.511 | 10.0 |
| **YOLOv12s @ 960 (shipped)** | C2A + VisDrone combined | 9.23 M | 23.2 | **0.864** | **0.774** | **0.833** | **0.577** | **26.2** |

> **Checkpoint provenance.** The YOLOv12s rows are `models/yolov12s.pt`, which records
> `epoch: 58` of a planned 100 (zero-indexed — 59 epochs completed) and
> `best_fitness 0.50397`. An earlier version of this file reported epoch 44 with
> P 0.845 / R 0.717 / mAP50 0.775 / mAP50-95 0.494. That was a superseded
> checkpoint. Verify with:
>
> ```python
> from ultralytics import YOLO
> m = YOLO('models/yolov12s.pt')
> print(m.model.names)   # must be a single class
> ```

⚠️ **The YOLOv12s rows are not comparable to the rows above them.** It was validated on the *combined* C2A + VisDrone validation set (2,591 images, 86,092 instances), which includes dense VisDrone city crowds that the C2A test set does not contain. A lower number on a harder set is not a worse model — but it is also not a better one until measured the same way.

---

## What the completed experiments actually prove

**1. Fine-tuning on disaster imagery is transformative, and this is measured, not asserted.**

A COCO-pretrained YOLOv8n finds fewer than one survivor in five (recall 0.189). Fine-tuned on C2A it finds nearly three in four (0.728). That is a **+286% relative gain in recall** from domain-specific training alone.

This is the single most useful result in the repository for the pitch. It answers "why not just use an off-the-shelf model?" with a number instead of an opinion.

**2. Scaling from nano to small buys real accuracy at ~2× the latency.**

YOLOv8n → YOLOv8s gains +0.036 recall and +0.056 mAP50-95 for 3.7× the parameters and 1.8× the inference time. Worth it on a GPU; the trade looks very different on a Raspberry Pi 4.

---

## The open question

**Is YOLOv12s actually better than the YOLOv8s already sitting in this repo?**

Right now that cannot be answered. The two were measured on different data. Three outcomes are possible:

- **YOLOv12s wins on C2A-only** → it is the demo model, and the combined-dataset training is vindicated.
- **YOLOv12s roughly ties** → the combined training still wins the argument, because it should generalise better to real drone footage that looks like neither dataset exactly. Worth stating explicitly rather than hiding.
- **YOLOv12s loses** → YOLOv8s is already trained, already faster, and becomes the demo model. Weeks of GPU time were spent learning something useful about architecture choice rather than producing the shipped artefact. That is an acceptable research outcome, but only if it is discovered before 10 September.

### Action

Validate YOLOv12s on the **C2A test split** — the identical split the YOLOv8 rows used — and add the row. Nothing else in this table changes.

```python
from ultralytics import YOLO
m = YOLO('models/yolov12s.pt')
r = m.val(data='c2a_test.yaml', split='test', max_det=1000)
print(r.box.mp, r.box.mr, r.box.map50, r.box.map)
```

Use `max_det=1000`. Every row above was produced with the default of 300, and C2A test averages 35 instances per image — dense scenes may have been truncated, which would understate recall across the whole table. If the YOLOv12s row is generated at 1000 while the others were at 300, the comparison is invalid again. Re-run the YOLOv8 rows at 1000 too, or state the setting per row.

---

## The Raspberry Pi 4 implication

The on-device benchmark target is a Raspberry Pi 4 Model B — CPU only, Cortex-A72.

YOLOv12s is 23.5 GFLOPs of an attention-heavy architecture. Attention is relatively slower on CPU than on GPU, so the Pi number will be worse than GFLOPs alone suggest.

**YOLOv8n is already trained and is 2.9× lighter (8.1 GFLOPs), at 4.4 ms/image on a T4.** If YOLOv12s does not clear a usable frame rate on the Pi, there is no need to train a new nano variant — the fallback already exists in this repo.

This supports a genuinely strong two-model story for the pitch:

- **YOLOv8n** — the onboard model. Light enough to run on the drone's companion computer for real-time triage.
- **YOLOv12s / YOLOv8s** — the ground-station model. Higher fidelity, re-runs the footage once it lands.

Both numbers measured, both disclosed. That reads as engineering judgement rather than a limitation being explained away.

### Benchmark plan

Run all three on the same Pi 4, same input size, same export format, and fill in this table:

| Model | Format | imgsz | ms/img | FPS | Notes |
|---|---|---|---|---|---|
| YOLOv8n | ONNX | 640 | | | |
| YOLOv8s | ONNX | 640 | | | |
| YOLOv12s | ONNX | 640 | | | |
| best of the above | NCNN | 640 | | | |
| best of the above | NCNN | 320 | | | |

---

## Notes on reproducibility

- The YOLOv12s confidence threshold is **~0.18**, deliberately low, chosen for recall over precision. The YOLOv8 rows were produced at Ultralytics defaults. State the threshold alongside any recall figure quoted from this table.
- `experiments/` weights are tracked in git today. New weights should be published as GitHub Release assets instead — see `.gitignore`.
- `YOLOv8s/C2A_finetuning/weights/last.pt` and `best.pt` are different files. Only `best.pt` matters now that training is finished.

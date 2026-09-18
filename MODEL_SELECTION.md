# Model Selection — Survivor Detection

*Resolved 24 Aug 2026 · owner: Dewang*

**Decision: YOLOv12s is the deployed detection model. YOLOv8n is the edge fallback if the Raspberry Pi 4 cannot sustain a usable frame rate.**


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

---

## The comparison

All three evaluated on the **same** C2A test split — 2,043 images, 72,523 instances — at `imgsz=640`, `max_det=1000`, `conf` left at the Ultralytics default so mAP is computed properly and P/R report at best-F1. Tesla T4.

| Model | Trained on | Epochs | Params | GFLOPs | P | R | mAP50 | mAP50-95 | ms/img |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| YOLOv8n | COCO (baseline) | — | 3.01 M | 8.1 | 0.312 | 0.189 | 0.131 | 0.060 | — |
| YOLOv8n | C2A | 50 | 3.01 M | 8.1 | 0.843 | 0.728 | 0.776 | 0.489 | **4.09** |
| YOLOv8s | COCO (baseline) | — | 11.16 M | 28.6 | 0.335 | 0.242 | 0.173 | 0.085 | — |
| YOLOv8s | C2A | 50 | 11.13 M | 28.4 | 0.861 | 0.764 | 0.814 | 0.545 | 8.84 |
| **YOLOv12s** | **C2A + VisDrone** | **60** | **9.23 M** | **23.2** | **0.869** | **0.790** | **0.834** | **0.572** | 12.84 |

*(COCO baseline rows are from the earlier run at `max_det=300`; the fine-tuned rows are all from the 24 Aug run at 1000.)*

---

## What this settles

**YOLOv12s wins every accuracy metric.** Against the next-best model (YOLOv8s) it gains +0.008 precision, **+0.026 recall**, +0.020 mAP50 and +0.027 mAP50-95.

**Recall is the metric that decides this**, because a missed survivor is the failure the system exists to prevent. YOLOv12s finds **790 of every 1,000** survivors against YOLOv8s's 764 — 26 more people located per thousand, on the same images.

**It also generalises more widely.** YOLOv12s was trained on C2A *plus* VisDrone and still beats models trained on C2A alone, on C2A's own test split. Broader training data cost it nothing on the narrower domain, which is the outcome the combined-dataset decision was betting on.

---

## Recall at the operating threshold

The table above reports P/R at the best-F1 point, which is what makes models comparable. **It is not where the system runs.** ARES runs at confidence 0.18, deliberately below the balanced point.

YOLOv12s at **960 px** on the **combined C2A + VisDrone val split** (2,591 images, 86,092 instances), read off the PR curve:

| Threshold | Precision | Recall | F1 | Missed per 1,000 |
|---|---:|---:|---:|---:|
| 0.37 — F1-optimal | 0.864 | 0.775 | **0.817** | 225 |
| **0.18 — ARES operating point** | 0.752 | **0.824** | 0.786 | **176** |

**Running at 0.18 rather than the F1 optimum finds 49 more survivors per thousand, at about 3 extra false alarms each.** Over the full split: +4,219 true positives for +12,893 false positives.

The comparison is deliberately against the F1 optimum rather than the 0.5 library default — beating a default proves nothing; leaving the best-balanced point on purpose is the actual decision.

> ⚠️ **Superseded measurement.** An earlier version of this table reported 0.831 at 0.18 against 0.740 at 0.5, measured on the **C2A test split** with a **superseded checkpoint**. It is not comparable to the table above: different split, different weights. The combined split includes dense VisDrone crowds that C2A does not, so a lower recall on it is a harder test, not a regression.

Two properties worth knowing:

**The threshold sits on a flat region, not a cliff.** Recall moves only 0.028 across the whole 0.10–0.25 range, so the system is insensitive to small changes here. A judge asking "what if your threshold is slightly wrong?" has a good answer.

**Lowering further is not worth it.** 0.18 → 0.10 buys 15 more survivors per thousand while adding false positives that become flicker tracks for the persistence filter to remove and extra postprocess cost on the Pi. 0.18 is where the trade stops paying.

> Note: passing `conf=` to `model.val()` does **not** give you this. Ultralytics reports P/R at best-F1 regardless, and filtering by confidence truncates the PR curve so mAP drops as an artefact rather than a real degradation. Read the confidence–recall curve from `curves_results`, or off `R_curve.png`.

---

## Honest caveats — state these, don't bury them

**The epoch counts are not equal.** YOLOv8n and YOLOv8s trained for 50 epochs; YOLOv12s reached 60 before Colab cut the session. This is not a controlled comparison. The margin is larger than 10 epochs would typically account for on an already-flattening curve, but it is not a clean architecture-versus-architecture result and should not be presented as one.

**`max_det` was not the problem after all.** These runs used 1000; the earlier YOLOv8 figures used the default 300. The numbers barely moved — mAP50 shifted by 0.002, recall not at all. **C2A test images do not exceed 300 detections**, so the cap was never binding on this dataset. Keep `max_det=1000` anyway: dense VisDrone-style scenes do exceed it, and a silent truncation there would read as poor recall.

**Training stops at epoch 60.** The model already wins decisively and the curve had flattened well before this point. With twelve days to the hackathon, the remaining epochs are worth less than the on-device benchmark and real demo detections — both of which are unstarted and both of which the pitch depends on.

---

## The speed finding, and what it means for the Pi

YOLOv12s has **fewer FLOPs than YOLOv8s (23.2 vs 28.4) but is 45% slower** — 12.84 ms against 8.84 ms.

That gap is the attention mechanism. YOLOv12's `A2C2f` blocks parallelise well on a GPU; FLOP count under-predicts their real cost. **On a Cortex-A72 with no such parallelism, expect the penalty to be worse than it is here**, not better.

Against the lightest model the ratio is starker: **YOLOv12s is 3.1× slower than YOLOv8n on a T4**, and likely more than that on the Pi.

### The two-model position

| Role | Model | Why |
|---|---|---|
| **Deployed / ground station** | YOLOv12s | Best recall. Runs where compute exists. |
| **Edge fallback** | YOLOv8n | 2.9× fewer FLOPs, 3.1× faster, and still finds 728 survivors per 1,000 |

If the Pi cannot sustain a usable rate with YOLOv12s, YOLOv8n is already trained and already measured — no new training required. That is a decision backed by numbers on a common split, not a guess.

---

## What to say in the pitch

**On model choice:**
> We evaluated three architectures on the same C2A test split — 2,043 images, 72,000 instances. YOLOv12s gave the best recall at 0.790, so it's the model we deploy. YOLOv8n is 3× faster and reaches 0.728, so it's our fallback if the onboard hardware can't sustain the heavier model. Both numbers are measured, not estimated.

**On why not an off-the-shelf model:**
> A COCO-pretrained YOLOv8n finds fewer than one survivor in five — recall 0.189. Fine-tuned on disaster imagery the same architecture reaches 0.728. That's a **285% relative gain in recall from training data alone**, and it's why domain-specific training matters more than architecture choice here.

**On the epoch imbalance, if asked:**
> The YOLOv8 models trained for 50 epochs and YOLOv12s for 60 — our Colab session ended there. So it isn't a controlled architecture comparison, and we don't present it as one. What it does establish is which model we should ship, which was the question we needed answered.

---

## Interim CPU benchmark — MacBook Air M5, 24 Aug

**Not the on-device figure.** A laptop is not a drone; this is a development measurement that de-risks the export path and gives a CPU baseline. The number that goes on the dashboard comes from the Raspberry Pi.

ONNX Runtime 1.29, CPU execution provider, 640 px, median of 30 runs after 5 warm-up calls. Test frame contains 2 people.

| Model | median | FPS | preprocess | inference | postprocess |
|---|---:|---:|---:|---:|---:|
| YOLOv12s | 97.4 ms | 10.3 | 1.64 ms | 88.9 ms | 0.54 ms |
| YOLOv8n | 44.7 ms | 22.4 | 1.39 ms | 36.5 ms | 0.45 ms |

**Both models export to ONNX and run cleanly.** YOLOv12s's attention blocks were the main deployment risk in this project — that risk is now closed.

**The CPU ratio is 2.18×, better than the 3.14× measured on the T4** and close to the 2.86× that raw FLOPs predict. The expectation that attention would be disproportionately expensive on CPU did not hold on an M-series core. **This does not transfer to a Cortex-A72** — different SIMD width, cache and clock — so the Pi figure must be measured, not extrapolated.

**Inference is 91% of total time.** Pre- and postprocessing are negligible, so any speedup must come from the model, the input size, or the runtime — not from pipeline tuning.

**Postprocess is understated here** because the test frame holds two people. It scales with detection count, and on a slow CPU with a crowded scene it becomes significant. The dashboard figure should be measured on a dense frame.

---

## Field findings — real VisDrone footage, 24 Aug

Three things measured on real drone video that were previously assumptions. All are pitch material.

### 1. The 40 m altitude limit is real

The README derives a maximum operating altitude of ~40 m from arithmetic: at 640 px input with a 60° FOV, a 1.7 m person spans 24 px at that height. Two VisDrone sequences confirmed it.

| Sequence | median box | median conf | above 0.70 conf |
|---|---|---:|---:|
| `uav0000086` (lower altitude) | 32 × 58 px | 0.615 | **31.8%** |
| `uav0000182` (higher altitude) | 13 × 24 px | 0.509 | **4.0%** |

At 24 px tall the detector is at the edge of what it can resolve. Detections stop being stable, and **unstable detections cannot be tracked by any tracker** — the higher clip produced 350 track IDs for roughly 22 visible people.

The limit was predicted from geometry and then observed in the field. That is a much stronger claim than a table.

### 2. Input size is the lever for small objects — and it has a ceiling

Same clip, same weights, same tracker; only `imgsz` changed. Detection runs on a 1280-wide clip, so at `imgsz=640` a 24 px person is downscaled to 12 px before the network sees them.

| imgsz | detections | unique IDs | median track | median conf | above 0.70 | seconds |
|---:|---:|---:|---:|---:|---:|---:|
| 640 | 5,502 | 350 | 8 | 0.509 | 4.0% | 41 |
| **960** | **7,081** | **333** | **11** | 0.530 | 5.6% | 61 |
| 1280 | 7,050 | 345 | 9 | 0.530 | 8.5% | 101 |

**Detection improved substantially: +29% detections, confidence above 0.70 more than doubled.** Tracking barely moved — 350 → 333 IDs.

The honest reading: input size was a real constraint but not the only one. Raising it recovers detections; it does not repair identity across occlusions. **960 is adopted** — it gives the best ID count at 40% less compute than 1280.

`DETECTION_IMGSZ = 960` is now a recorded constant. The shipped detections were produced at that size, so **the on-device benchmark must target 960**, not 640. That is 2.25× the pixels, and it may push YOLOv12s out of reach on a Pi 4 and make YOLOv8n the onboard model.

### 3. The persistence threshold is a duration, not a frame count

The rule is "a track must persist before we call it a survivor." The rule was first written as `min_frames = 3`, justified as *two seconds at 1.5 FPS on the Pi*.

**That justification is frame-rate dependent and the constant was not.** On 24 fps footage, 3 frames is an eighth of a second and filters almost nothing:

| min_frames | survivors | at 24 fps |
|---:|---:|---|
| 3 | 258 | 0.13 s — filters nothing |
| 10 | 173 | 0.4 s |
| 30 | 79 | 1.25 s |
| **60** | **23** | **2.5 s** |

Against ~22.7 detections per frame, 60 frames returns 23 confirmed survivors — the first figure in line with what is visible on screen.

Expressed correctly:

```python
MIN_TRACK_SECONDS = 2.5
MIN_TRACK_FRAMES  = int(MIN_TRACK_SECONDS * CLIP_FPS)   # 60 at 24 fps, 3 at 1.5 fps
```

Same rule, same meaning, at any frame rate — including the Pi's. **The original `min_frames = 3` was accidentally correct for the Pi and wrong everywhere else.**

---

## Outstanding

- [x] **Qualcomm AI Hub benchmark — DONE.** YOLOv12s INT8 at both 640 and 960 on two
  Dragonwing boards. See `experiments/QUALCOMM_BENCHMARK.md` and
  `experiments/ARES_MEASURED_NUMBERS.md`. Headline: **4.8 FPS at 960 on RB3 Gen 2,
  16.3 FPS on IQ-9075, 489/489 layers (100 %) on the Hexagon NPU on every run.**
- [ ] **Pi 4 benchmark** — YOLOv12s and YOLOv8n, ONNX at 960 and 640, on both a sparse
  and a dense frame, with active cooling. Still the one unmeasured field on the
  dashboard; Qualcomm numbers do not fill a Pi row. **Do not carry over the old
  "0.5–1 FPS" guess** — that was an extrapolation, and this project has now had three
  extrapolations overturned by measurement (cluster spread, the ONNX compile failure,
  and the 640 device latency, which came in 3× faster than predicted). Measure it.
- [ ] **INT8 accuracy** — every device latency above is INT8; every accuracy figure is
  FP32. They are two different models until this is measured.
- [ ] **YOLOv8n scaling control** — v8n is pure convolution. Benchmarking it at 640 and
  960 on the RB3 would settle whether v12s's 7.82× resolution penalty is attention's
  quadratic term or a memory-tiling effect. Two exports, four jobs.
- [x] ~~**Recall at the operating threshold**~~ — re-measured 26 Aug at 960 px on the combined split: **0.824 at conf 0.18**, against 0.775 at the F1-optimal 0.37. See above.
- [ ] **Real detections** — run YOLOv12s over demo footage, replace the synthetic fixture.

---

## Reproducing this

```python
from ultralytics import YOLO
YOLO(weights).val(data="c2a.yaml", split="test", max_det=1000,
                  imgsz=640, batch=16, device=0)
```

Any future row added to this table must use the same split, the same `max_det`, and the same image size — recording those three is what makes the comparison mean anything. The earlier ambiguity in this document existed precisely because a row was added that had been measured differently.

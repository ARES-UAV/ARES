# RGB + thermal fusion — what to do

---

## 1. Why your two datasets cannot do it

HIT-UAV and AIResQ are **thermal only**. C2A and VisDrone are **RGB only**.
Fusion needs the *same scene* in both modalities, pixel-registered, so a box in
one image means the same ground position in the other.

No amount of work on the data you have produces that. It needs a paired set.

---

## 2. What "fusion" means here — and it is easier than it sounds

There are two kinds, and the plan document already picked one:

```
C_fused = w_r · C_RGB + w_t · C_thermal          w_r + w_t = 1
```

That is **late fusion** — decision level. Both detectors run independently,
their boxes get matched to each other, and the confidences combine.

**It is not early fusion** (stack RGB + thermal into a 4-channel tensor, train
one network on it). Early fusion usually scores a point or two higher in
papers. Late fusion wins here for three reasons that matter more:

| | |
|---|---|
| **It uses the models you already have** | Early fusion means a new architecture and a full training run. You have a working RGB detector and a working thermal detector. |
| **It degrades gracefully** | Lose the thermal camera in flight and the RGB detector keeps working. A 4-channel network handed a dead channel does something undefined. |
| **It is explainable** | *"Both sensors saw something here"* is a sentence a judge can check. A learned cross-modal feature map is not. |

So: **no new model. You need paired imagery to evaluate, and a short fine-tune
so each detector has seen that domain.**

---

## 3. The dataset

**LLVIP** — 15,488 visible-infrared pairs, *strictly aligned in time and
space*, pedestrians labelled, night scenes. It is the standard benchmark for
exactly this.

Download needs a form (name, institution, country) — non-commercial research
use. → [bupt-ai-cz.github.io/LLVIP](https://bupt-ai-cz.github.io/LLVIP/)

**The honest caveat, and say it before a judge does:** LLVIP is street-level
surveillance, not aerial. Your fusion result will be a *mechanism*
demonstration on the standard benchmark, not a UAV result. Fixing that needs a
paired aerial dataset, and no good one exists for person detection —
[UAV-TIRVis](https://pmc.ncbi.nlm.nih.gov/articles/PMC12734084/) is registration
research, not a detection benchmark.

---

## 4. The steps

**1 · Get LLVIP** (~30 min including the form)

**2 · Fine-tune each detector onto the domain** (~4–6 h GPU total)

Short runs — 25–30 epochs each. Both models are already person detectors; this
is adaptation, not training.

```bash
yolo detect train model=models/yolov12s.pt data=llvip_visible.yaml \
     epochs=30 imgsz=960 name=rgb_llvip
yolo detect train model=<thermal best.pt> data=llvip_infrared.yaml \
     epochs=30 imgsz=960 name=ir_llvip
```

Keep them **separate**. Two models, one per modality — that is what late fusion
is.

**3 · Predict on the test split, both models, same images**

Write out the team's contract format plus `image_id`:

```json
{"image_id": "190001", "bbox": [x1,y1,x2,y2], "confidence": 0.87, "class": 0}
```

**4 · Fuse and evaluate** — `tools/fuse_eval.py`, already written and tested

```bash
python tools/fuse_eval.py --rgb rgb_preds.json --thermal ir_preds.json \
                          --gt llvip_test_gt.json --w-rgb 0.5
```

**5 · Sweep the weight.** `--w-rgb 0.3 / 0.4 / 0.5 / 0.6 / 0.7`. Report the
value you picked and why, the same way conf 0.18 was picked off a PR curve.

---

## 5. What the result will look like — plan the framing now

**Expect thermal to beat RGB by a wide margin, and fusion to land near
thermal.** LLVIP is all night scenes. That is a *"thermal works in the dark"*
result, which nobody doubts, and it is **not** a fusion result.

The number that earns fusion its place is **false positives at equal recall.**

Two systems at different operating points cannot be compared on false positives
directly. Hold recall equal, then count. `fuse_eval.py` does this automatically
and prints it as the second table.

**Why it works:** a detection seen by only one sensor gets the other's vote as
zero, so it is penalised. A hot car reads as a person to thermal alone; RGB not
confirming it drops it below threshold. Agreement is rewarded, single-sensor
guessing is not.

On synthetic data built to have thermal-only false positives, the evaluator cut
them **85 → 22 at identical recall**. That confirms the mechanism works; it
predicts nothing about LLVIP.

### The sentence you are aiming for

> *"On LLVIP, thermal alone reaches R recall with F false positives. Fusing the
> RGB detector's confidence holds the same recall at F′ — a P % reduction —
> because a detection only one sensor believes is down-weighted. Measured, not
> assumed."*

---

## 6. Cost, and whether to do it

**Roughly 1.5–2 days**, most of it GPU time you can leave running.

| | |
|---|---|
| Download + prepare LLVIP | 1–2 h |
| Two fine-tunes | 4–6 h GPU, unattended |
| Predict + fuse + sweep | 2–3 h |
| Write-up | 1 h |

It competes with: rendering the video, hazard classifier metrics, the deck, and
**the full dry run**.

### My read

The thermal detector alone already moves "Multi-sensor fusion: Partial" to a
defensible position — you have a working thermal person detector at 0.883
recall, and that is the night capability the pitch describes.

Fusion adds a *measured mechanism* on top. It is genuinely stronger, and it is
also the item most likely to overrun.

**Do it if the video and the dry run are finished first.** If they are not,
split the scope row honestly and put fusion in the 30 September window, where
there is room to do the paired-aerial version properly rather than the
street-level proxy.

Do not start it three days before the 10th.

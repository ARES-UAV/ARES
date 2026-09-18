# Thermal detection model

**Trained:** ~31 August 2026 · owner: Dewang
**Architecture:** YOLOv8s, single `Person` class
**Run:** 104 epochs of a planned 150 · ~23.6 h wall clock
**Source:** `results.csv` from the Ultralytics run

---

## 1. Result

Final epoch (104), on the validation split:

| Metric | Thermal (this model) |
|---|---:|
| Precision | **0.921** |
| Recall | **0.883** |
| mAP50 | **0.927** |
| mAP50-95 | **0.554** |

Best mAP50-95 was **0.55403 at epoch 101**, against 0.55353 at 104 — the same
number. Either checkpoint is the model; Ultralytics' `best.pt` will hold 101.

---

## 2. Training is finished — stop at 104

The run was planned for 150 epochs. It does not need them.

| epochs | mean mAP50-95 |
|---|---:|
| 1–10 | 0.396 |
| 11–20 | 0.472 |
| 21–30 | 0.501 |
| 31–40 | 0.521 |
| 41–50 | 0.532 |
| 51–60 | 0.541 |
| 61–70 | 0.544 |
| 71–80 | 0.550 |
| 81–90 | 0.553 |
| 91–100 | 0.552 |
| 101–104 | 0.554 |

**Over the last 25 epochs mAP50-95 moved +0.0019, and its entire range was
0.0032.** That is noise, not learning. The remaining 46 epochs would cost
roughly ten hours of GPU for a change too small to report.

> **Recommendation: stop the run and ship `best.pt` from epoch 101.**

### Provenance note

The `time` column resets at epoch 91 — 73,457 s back to 939 s. Training was
interrupted and resumed there. The metrics continue smoothly across the join,
so the resume was clean, but the two halves are separate sessions and total
wall time is the sum of both.

---

## 3. The datasets

Combined, mirroring the C2A + VisDrone strategy used for the RGB model.

| | **HIT-UAV** | **AIResQ** |
|---|---|---|
| Published | *Sci Data* 2023 | *Sci Data* 2026 |
| Images | 2,898 thermal IR | 9,788 thermal IR |
| Resolution | — | up to 2048 × 1536 |
| Annotations | 24,899 objects, 5 classes | 17,550 person boxes |
| Viewpoint | **real UAV**, high altitude | elevated structures — cable cars, towers, bridges, **50–120 m** |
| Classes used | Person only | Person only |

≈ **12,686 images**, both thermal, both aerial or aerial-like.

### Two things to disclose rather than let a judge find

**AIResQ is not filmed from drones.** The authors captured it from fixed
elevated structures to *simulate* an airborne viewpoint. It is representative
of drone imagery; it is not drone imagery. Given that we already disclose
borrowing VisDrone flight for the RGB demo, saying this costs nothing and
protects the rest of the claim.

**HIT-UAV ships five classes and we used one.** Car, Bicycle, OtherVehicle and
DontCare were dropped so the thermal model matches the RGB model's single
`Person` class. That is the right call — the data contract has `class: 0` and
nothing downstream knows what a bicycle is — but it means our numbers are not
comparable to any published HIT-UAV benchmark, which will be multi-class.

---

## 4. Against the RGB model — and why it is not a comparison

| | Thermal · YOLOv8s | RGB · YOLOv12s @960 |
|---|---:|---:|
| Precision | **0.921** | 0.864 |
| Recall | **0.883** | 0.774 |
| mAP50 | **0.927** | 0.833 |
| mAP50-95 | 0.554 | **0.577** |

**Do not present this as thermal beating RGB.** Different datasets, different
validation splits, different architectures, different scene difficulty. The
only honest reading is of the *shape*:

**Thermal detects more easily and localises less precisely.** A warm body on
cool ground is a high-contrast blob — easy to find, which is the mAP50 and
recall. But a blob has soft edges, so a tight box is harder to place, which is
the mAP50-95 falling below RGB's despite every other metric being higher.

That pattern is what thermal imaging should produce, and it is worth saying out
loud: it is evidence the model learned the physics rather than overfitting.

### The altitude point, which is genuinely useful

The RGB model has a stated ceiling near **40 m** — above it a person spans
under ~24 px and detection collapses. AIResQ was captured at **50–120 m** and
the thermal model reaches 0.883 recall on it.

Thermal does not need pixels to resolve a face or limbs. It needs a temperature
difference. **So thermal extends the usable operating altitude past where RGB
stops**, which is a real capability argument and not a marketing one.

Worth measuring properly before it is claimed: recall against altitude on the
AIResQ split, the same way the RGB ceiling was established.

---

## 5. What this is, and what it is not

**This is a thermal person detector.** It works, it is measured, and it is the
night-and-smoke capability the pitch has been describing as Partial.

**It is not multi-sensor fusion**, and the scope table must not move to Built on
the strength of it.

Fusion, as the SIH plan asks for it, means measuring three things on the
**same scenes**:

```
RGB only        recall, false positives, localisation error
thermal only    recall, false positives, localisation error
RGB + thermal   recall, false positives, localisation error
```

Neither HIT-UAV nor AIResQ carries registered RGB alongside the thermal, so no
part of that comparison can be run on this data. It needs a **paired** dataset —
LLVIP, KAIST Multispectral, FLIR ADAS and M3FD all provide aligned RGB/thermal
pairs — and a separate training run.

### Scope table, corrected

| Capability | Status |
|---|---|
| Thermal person detection | **Built** — YOLOv8s, 0.883 recall, measured |
| RGB + thermal fusion | **Not built** — needs paired imagery; no fusion experiment has been run |

Splitting the row is more honest than either claiming fusion or hiding a
working thermal detector inside a "Partial".

---

## 6. Still needed before these numbers are quotable

The RGB figures carry their provenance — *"2,591 images · 86,092 instances"*.
These do not yet.

1. **Validation split size** — how many images and person instances is 0.883
   recall measured over? Without it the number cannot be defended.
2. **The split itself** — was it a random split of the combined pool, or held
   out per dataset? A random split across two datasets of very different size
   (2,898 vs 9,788) mostly measures AIResQ.
3. **Per-dataset breakdown** — recall on HIT-UAV alone and AIResQ alone. If
   they differ sharply, the combined number hides it, and a judge asking
   "does it work on real drone footage?" needs the HIT-UAV row specifically.
4. **Operating threshold.** The RGB model runs at conf 0.18, chosen off the PR
   curve for recall. The thermal model has no chosen threshold yet — the PR
   curve exists, so pick one the same way and record the trade.

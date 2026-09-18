# YOLOv8s vs YOLOv12s on C2A + VisDrone — settled

**Three runs, 12–13 September 2026.** All on the combined C2A + VisDrone
validation split, default `max_det` 300, single `human` class.

| folder | what it is | imgsz |
|---|---|---|
| `train/` | YOLOv8s, 100 of 100 epochs, 36.1 h across 7 sessions | 960 |
| `val-6/` | YOLOv12s re-validation of the shipped checkpoint | 960 |
| `val-5/` | YOLOv8s, same checkpoint, smaller input | 640 |

Trained on a teammate's machine (`C:\Users\subha\…`), resumed from `last.pt`;
`best.pt` and `last.pt` are byte-identical in size and timestamp, consistent
with best == last == epoch 100.

---

## 1. Two things are now confirmed that were open yesterday

**① The v12s re-validation reproduces the shipped number exactly.**
`val-6` gives **mAP50 0.833** against the 0.833 in
`ARES_MEASURED_NUMBERS.md`. The shipped figures were produced at the default
`max_det=300`, the same as the v8s run. **The comparison is valid.**

**② All three runs are on the same split, proved by arithmetic.** Every
confusion matrix sums to the same ground-truth total:

```
YOLOv8s @960    71,147 TP  +  14,945 FN  =  86,092
YOLOv12s @960   70,884 TP  +  15,208 FN  =  86,092
YOLOv8s @640    65,496 TP  +  20,596 FN  =  86,092
```

86,092 is the documented instance count. No assumption required.

---

## 2. The result, counted in people

At the confusion-matrix operating point, over 86,092 labelled people:

| | TP | FP | FN | recall | precision | mAP50 |
|---|---:|---:|---:|---:|---:|---:|
| **YOLOv8s @960** | **71,147** | **13,103** | **14,945** | **0.8264** | **0.8445** | **0.8453** |
| YOLOv12s @960 | 70,884 | 15,376 | 15,208 | 0.8234 | 0.8217 | 0.8330 |
| YOLOv8s @640 | 65,496 | 13,535 | 20,596 | 0.7608 | 0.8287 | 0.7700 |

**YOLOv8s @960 vs the shipped YOLOv12s @960:**

```
+263 more people found      −2,273 fewer false alarms
recall +0.0031              precision +0.0227
```

**The win is precision, not recall.** v8s finds essentially the same people and
raises **2,273 fewer false alarms** doing it. On a system deliberately tuned for
recall at conf 0.18 — where the stated price is *"about three false alarms per
extra person found"* — a model that removes 2,273 false alarms for free is
buying back roughly 758 people's worth of that trade.

Best-F1 operating points, for the record: v8s @960 **0.353**, v12s @960
**0.371**, v8s @640 **0.334**. ARES runs at 0.18, well below all three.
Off the v8s recall–confidence curve, recall at conf 0.18 reads **≈0.84** against
v12s's documented 0.824 — **estimated from the plot, not measured.** Run
`val(conf=0.18)` before that number goes anywhere.

---

## 3. The 640 hypothesis is dead, and it failed in the direction nobody predicted

Yesterday's reasoning was: *YOLOv12s is attention-heavy and attention is
quadratic in token count, so it has the most to lose from a smaller input.
YOLOv8s is pure convolution — it may lose less.*

**That prediction was wrong. YOLOv8s lost more.**

| | @960 | @640 | loss |
|---|---:|---:|---:|
| YOLOv12s | 0.8330 | 0.7830 | **−0.0500  (−6.0 %)** |
| YOLOv8s | 0.8453 | **0.7700** | **−0.0753  (−8.9 %)** |

v8s degrades **1.5× as badly**, and at 640 it ends up **below** v12s at 640
(0.770 vs 0.783) despite being ahead at 960.

In people: dropping v8s from 960 to 640 costs **5,651 additional missed
survivors** out of 86,092 — recall falls 0.8264 → 0.7608.

**Why the reasoning failed.** The bottleneck here is not architecture, it is
pixels on target. These are aerial images of people who are already tiny; the
RGB model's stated ceiling is about 40 m altitude, where a person spans ~24 px.
Halving the input halves that again. No architecture recovers detail that was
never sampled — and attention appears to help *aggregate context* for small
objects rather than hurt.

### What that means for the project

**The 4.8 FPS operating point stands.** The half-day of work that looked like it
might dissolve the biggest constraint in ARES instead confirms the constraint is
real:

- the frame-rate study's premise holds — 960 is not optional
- BoT-SORT remains the right tracker, for the reasons already measured
- the "one model or two on the drone" trade is unchanged
- `imgsz 960` in `backend/config.py` is now justified by **two** models, not one

That is a less exciting result than the alternative and a more useful one. It
closes a question that would otherwise have been re-opened by the first person
to ask *"why not just run at 640 and go seven times faster?"* — and the answer
is now a number: **5,651 people.**

---

## 4. Where the two models actually stand

| | YOLOv8s | YOLOv12s (shipped) |
|---|---:|---:|
| Params | 11.13 M | **9.23 M** |
| GFLOPs | 28.4 | **23.2** |
| Epochs trained | 100 / 100 | 59 / 100 |
| Recall @960 | **0.8264** | 0.8234 |
| Precision @960 | **0.8445** | 0.8217 |
| mAP50 @960 | **0.8453** | 0.8330 |
| mAP50 @640 | 0.7700 | **0.7830** |
| RB3 latency @960 | **not measured** | 209.5 ms · 100 % on NPU |

**Dewang's August hypothesis, final score.** *Same or better with equal
training* — **correct**. *Much lighter, producing more FPS* — **not
established, and unlikely on the paper specs**: v8s carries 21 % more
parameters and 22 % more FLOPs. Whether pure convolution beats attention on the
Hexagon NPU is still an open, measurable question.

### Still missing

- **mAP50-95 for `val-5` and `val-6`.** Neither val run saved a CSV or JSON, so
  only what the plots print survives. Re-run with the metrics captured, or the
  comparison stays incomplete on the strictest metric.
- **v8s on-device latency.** Nothing has been benchmarked. The entire
  deployment case for a swap rests on this and it does not exist yet.
- **INT8 accuracy** for either model.

---

## 5. Decision: keep YOLOv12s shipped. Benchmark v8s — and the case for doing so is stronger than the accuracy table

### Why not swap now

A +0.023 precision gain does not justify re-opening `detections.json` seventeen
days from submission. A model swap re-derives **every downstream number**: the
23 confirmed survivors, the 333 track IDs, the 7,081 raw detections, the whole
frame-rate study, every count on the dashboard, the demo video, and the figures
already in the SIH deck. The pre-registered swap rule in `MODEL_SELECTION.md`
was conditioned on discovering this **before 10 September**; it is the 13th.

### Why the FPS question is worth taking seriously anyway

**FLOPs do not predict latency for attention models, and this repository already
has the measurement that proves it.** From the model table, both at 640 on a
Tesla T4:

| | GFLOPs | ms / image |
|---|---:|---:|
| YOLOv8s | 28.4 | **8.84** |
| YOLOv12s | 23.2 | 12.84 |

**YOLOv8s carries 22 % more FLOPs and runs 1.45× faster.** Attention is
memory-bandwidth-bound, not compute-bound, so it under-delivers relative to its
FLOP count on real silicon.

That matters here because the RB3's own scaling is already anomalous.
`ARES_MEASURED_NUMBERS.md` records YOLOv12s scaling **7.38×** from 640 to 960 on
the RB3 — above attention's quadratic ceiling of 5.06× — and labels the cause
*"not established"*. If that penalty is attention, a pure-convolution model
should scale close to the pixel-count ratio of 2.25× instead.

**Carrying the T4 ratio across and applying convolution-like scaling — a
prediction, explicitly not a measurement:**

| | latency @960 | FPS | vs shipped |
|---|---:|---:|---:|
| YOLOv12s — measured | 209.5 ms | **4.8** | — |
| YOLOv8s — if it scales 2.25× | ~44 ms | ~22.7 | 4.8× |
| YOLOv8s — if it scales 3.0× | ~59 ms | ~17.0 | 3.6× |
| YOLOv8s — if it scales 4.0× | ~78 ms | ~12.8 | 2.7× |

Every row of that table is inference from two ratios. It could be wrong — NPU
behaviour is not GPU behaviour, and the RB3's anomaly may be memory tiling
rather than attention, in which case v8s pays the same penalty and the whole
prediction collapses. **That is precisely why it is worth half a day to find
out rather than to argue about.**

### What more FPS would actually buy — and what it would not

Not coverage. At 4.8 FPS the aircraft already gets **~22 looks at every patch of
ground**, and `ARES_MEASURED_NUMBERS.md` states the conclusion: *"compute is not
the binding constraint; the remaining hard problem is per-look recall."* Going
to 22 FPS and ~106 looks finds nobody new by that route.

Two things it does buy, and both are currently broken:

1. **Counting.** `FRAME_RATE_STUDY.md`'s conclusion is that *finding* survivors
   at 4.8 FPS is solved but *counting them once* is not — every tracker
   configuration either misses people or splits them. That failure is caused by
   frame rate, and it is the one open defect in the perception chain.
2. **Fusion headroom.** Running RGB and thermal together drops the drone to
   2.4 FPS, where ByteTrack collapses to **0 of 19** survivors and BoT-SORT
   loses one. SIH requires multi-sensor fusion. Headroom here converts a
   compromise into a non-issue.

### The decision rule, written before the measurement

| v8s @960 on RB3 | Verdict |
|---|---|
| **< 70 ms** (> 14 FPS) | Transformative. Swap in Phase 2, immediately after 30 September. Quote it in the deck now as *measured, not yet shipped*. |
| **70 – 150 ms** | Real but not decisive. Record it; do not swap before submission. |
| **> 150 ms** | YOLOv12s stays. The architecture question is closed for good. |

Writing the thresholds down first is what made the § 3 result trustworthy. The
same applies here.

### The work, in order

| | Work | Time |
|---|---|---|
| **A** | Export v8s to ONNX INT8 · benchmark @960 **and** @640 on RB3 via AI Hub | half a day |
| **B** | Re-run `val-5` / `val-6` with metrics saved, to recover mAP50-95 | 40 min |
| **C** | `val(conf=0.18)` on v8s @960 — the operating point ARES actually uses | 20 min |
| **D** | Publish the v8s weights to a GitHub Release | 20 min |

**A also settles the open NPU-scaling question** in
`ARES_MEASURED_NUMBERS.md` — benchmarking a pure-convolution model at both
sizes on the same device is the experiment that file already specifies. One run,
three answers: the model choice, the scaling mechanism, and whether 4.8 FPS is
an architectural limit or a fundamental one.

---

## 6. What to say in the deck

Nothing changes today. If A lands before the 27th, one line earns its place:

> *"We retrained YOLOv8s on the same data, same split and same input size as a
> controlled comparison, tested both at reduced resolution, and benchmarked on
> the target silicon before choosing. The architecture and the input size are
> measured decisions, not inherited ones."*

The 640 result is worth a sentence of its own if a judge asks about frame rate:

> *"We measured it. Running at 640 would be 7× faster and would miss 5,651 more
> people out of 86,092. We stayed at 960."*

---

## 7. Record of a failed prediction

Yesterday this file predicted that YOLOv8s would degrade more gracefully at 640
because it is pure convolution. The measurement says the opposite, by 1.5×.

The prediction is left written down rather than quietly deleted. That is the
same practice that caught the epoch 44→58 error, the `bytetrack-wide` false
fix, and the multi-sortie counter bug — and it is the reason the numbers in this
repository can be trusted.

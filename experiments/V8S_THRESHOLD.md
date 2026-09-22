# Choosing the operating threshold for YOLOv8s

**Answer: `conf = 0.18`. Unchanged.**

Not inherited — re-derived from the v8s curve using the same rule that produced
0.18 for YOLOv12s, and it lands in the same place.

---

## How the numbers were obtained

Neither val run saved a CSV, so the P/R-vs-confidence curves were read back out
of the rendered plots (`BoxP_curve.png`, `BoxR_curve.png`) by locating the axis
frame and the "all classes" line.

**The method was validated before it was used.** Run on YOLOv12s, it reproduces
the figures already in `ARES_MEASURED_NUMBERS.md`:

| | documented | extracted | delta |
|---|---:|---:|---:|
| conf 0.371 precision | 0.864 | 0.863 | −0.001 |
| conf 0.371 recall | 0.775 | 0.774 | −0.001 |
| conf 0.18 precision | 0.752 | 0.749 | −0.003 |
| conf 0.18 recall | 0.824 | 0.824 | +0.000 |

Good enough to choose a threshold. **Not good enough to publish** — see § 4.

---

## The rule, restated

`ARES_MEASURED_NUMBERS.md` fixes the principle: *"about three false alarms for
every extra person found. An operator dismisses a false box in a second; a
missed survivor is not recoverable."*

That 3:1 is not arbitrary — it is what YOLOv12s actually paid going from its
F1-optimal threshold down to 0.18. So the rule is: **lower the threshold from
the F1-optimal until the cumulative cost reaches ≈3 false alarms per additional
person found, and stop.**

---

## Applying it to YOLOv8s

F1-optimal for v8s is **0.353** (v12s's was 0.371). Cost of going below it,
over 86,092 labelled people:

| conf | precision | recall | + found | + false alarms | cumulative FP/person | marginal |
|---:|---:|---:|---:|---:|---:|---:|
| 0.353 | 0.872 | 0.785 | — | — | — | — |
| 0.30 | 0.852 | 0.799 | 1,195 | 2,086 | 1.75 | 1.75 |
| 0.25 | 0.827 | 0.811 | 2,231 | 4,723 | 2.12 | 2.54 |
| 0.22 | 0.808 | 0.818 | 2,826 | 6,835 | 2.42 | 3.55 |
| 0.20 | 0.793 | 0.822 | 3,234 | 8,555 | 2.65 | 4.22 |
| **0.18** | **0.777** | **0.827** | **3,673** | **10,600** | **2.89** | 4.65 |
| 0.15 | 0.747 | 0.835 | 4,325 | 14,479 | **3.35** | 5.95 |
| 0.12 | 0.708 | 0.843 | 5,036 | 20,123 | 4.00 | 7.93 |

**0.18 sits at 2.89 — inside the 3:1 envelope. 0.15 breaches it at 3.35, and
its marginal rate is 5.95.**

The same rule, applied independently to a different model's curve, returns the
same threshold. That is a result worth stating rather than a coincidence worth
hiding.

### The line for the deck, updated

> *"We run at 0.18, not the F1-optimal 0.353. It costs 9.5 points of precision
> and buys 4.2 points of recall — about three false alarms for every extra
> person found. We picked it off the curve, not from a default."*

---

## Why not exploit v8s's better precision to go lower

There is a tempting alternative: v8s is more precise at every threshold, so it
could run at **0.154** and produce the *same* false-alarm count v12s produced at
0.18 — 23,776 against 23,761 — while finding **822 more people**.

Rejected, for two reasons:

1. **It breaks the rule to do it.** The marginal cost of that last stretch is
   5.95 false alarms per person, double the accepted 3:1. Choosing it means
   quietly changing the operating principle to justify a number, which is the
   opposite of how 0.18 was arrived at.
2. **It changes two variables at once.** If the detector swap goes ahead and the
   confirmed survivor count moves off 23, that has to be attributable to the
   model. Change the threshold in the same commit and the result is
   unanalysable — the same confound that made the original v8s-vs-v12s
   comparison meaningless until this week.

Hold conf fixed. Swap one thing. Measure.

---

## What v8s at 0.18 actually delivers

Against the shipped YOLOv12s at the same threshold, over 86,092 people:

```
YOLOv12s @0.18    finds 70,957    23,761 false alarms
YOLOv8s  @0.18    finds 71,228    20,480 false alarms
                       +272          −3,281
```

**Better on both axes at once — no trade.** 272 more people found *and* 3,281
fewer false alarms. That is the whole case for the swap in one line, and it does
not depend on the latency benchmark at all.

---

## The two config values, if the swap goes ahead

```python
# backend/config.py
DETECTION_CONF = 0.18          # unchanged — re-derived, not inherited
```

```python
# simulation/config.py
P_DETECT = 0.827               # was 0.824 (YOLOv12s recall at conf 0.18)
```

**The simulation change is +0.003.** The 100-seed re-run is still required for
correctness, but the headline figures — 20/20 vs 11/20, the 3.11× speed-up —
will move by almost nothing. That is a meaningful reduction in the swap's blast
radius: the deck chart is unlikely to need redrawing.

---

## Before any of this is quoted

These figures are read off plots. The repo's standard is a number traceable to
an artefact you can re-read, so confirm them first-hand:

```bash
yolo detect val model=models/yolov8s_c2a_visdrone.pt data=<combined.yaml> \
     imgsz=960 conf=0.18 save_json=True
```

Takes twenty minutes and produces the real precision, recall and mAP50-95 at the
operating point — including the mAP50-95 that `val-5` and `val-6` lost by not
saving their metrics. Until then, treat everything above as **derived from
plots, sufficient to decide, not yet publishable.**

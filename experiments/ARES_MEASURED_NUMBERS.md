# ARES — the measured numbers

Single source of truth. Every figure here was measured; nothing is estimated.
Anything not measured is listed at the bottom under **Not measured**, and must
be labelled that way wherever it appears.

Last updated: 26 August 2026

---

## Model

**YOLOv12s**, single class (`{0: 'human'}`), 9,231,267 parameters.
Trained on combined **C2A + VisDrone**. Shipped weights: `models/yolov12s.pt`.

Read directly out of the checkpoint, not from notes:

```
epoch          58        (zero-indexed → 59 completed, of a planned 100)
epochs         100
best_fitness   0.50397
```

> **Corrected 26 Aug.** Six files claimed "epoch 44 of 100" with weaker
> accuracy figures. Those came from a superseded checkpoint and were never
> re-checked against the file. Training had run 15 epochs further than the
> notes recorded. Nothing was fabricated — a note was written once and
> believed thereafter. **Every number in this file is traceable to an
> artefact you can re-read.**

Ship configuration (`backend/config.py`):

| Setting | Value |
|---|---|
| `imgsz` | 960 |
| `conf` | 0.18 |
| `max_det` | 1000 |
| Tracker | ByteTrack |

---

## Accuracy — FP32

Combined C2A + VisDrone validation split.
**2,591 images · 86,092 person instances.** Same checkpoint at both sizes.

| Metric | 640 | **960 (shipped)** |
|---|---|---|
| Precision | 0.854 | **0.864** |
| Recall | 0.727 | **0.774** |
| mAP50 | 0.783 | **0.833** |
| mAP50-95 | 0.511 | **0.577** |

### Decomposing the gain

Three measurements separate two variables that would otherwise be confounded:

```
mAP50-95   0.494   →   0.511   →   0.577
           ep44         final       final
           @640         @640        @960
                     └───────┘  └──────────┘
                     training     resolution
                      +0.017        +0.066
```

**Resolution accounts for ~80 % of the improvement, finishing training ~20 %.**

---

## The confidence threshold

Measured off the validation PR curve at 960:

| | conf 0.37 (F1-optimal) | **conf 0.18 (shipped)** |
|---|---|---|
| Precision | 0.864 | 0.752 |
| Recall | 0.775 | **0.824** |
| F1 | 0.817 | 0.786 |

Over 86,092 instances:

```
conf 0.37    TP 66,721    FP 10,502
conf 0.18    TP 70,940    FP 23,395
             ─────────    ─────────
             +4,219       +12,893
```

> **≈ 3 extra false alarms per additional survivor found.**

The line: *"We run at 0.18, not the F1-optimal 0.37. It costs 11 points of
precision and buys 5 points of recall — about three false alarms for every extra
person found. An operator dismisses a false box in a second; a missed survivor is
not recoverable. We picked it off the curve, not from a default."*

---

## On-device — Qualcomm AI Hub

Real hosted silicon. **INT8** weights and activations, `qnn_context_binary`.

| | RB3 Gen 2 (QCS6490) | IQ-9075 EVK (QCS9075) |
|---|---|---|
| **960** | 209.50 ms · **4.8 FPS** | 62.30 ms · **16.1 FPS** |
| **640** | 28.40 ms · 35.2 FPS | 14.04 ms · 71.2 FPS |
| 960 → 640 ratio | 7.38× | 4.44× |
| Peak memory (960 / 640) | 3–7 / 3–6 MB | 2–6 / 6.5 MB |
| **NPU coverage** | **489/489 — 100 %** | **489/489 — 100 %** |

**Every latency is a MEDIAN of ~100 samples.** AI Hub's
`estimated_inference_time` — and the "Minimum Inference Time" figure on its
console — is the fastest of the hundred. This repo published minimums for a
fortnight:

| Run | Minimum | Median | Overstated by |
|---|---:|---:|---:|
| RB3 @ 960 | 207.6 ms | 209.5 ms | 0.9 % |
| IQ-9075 @ 960 | 61.4 ms | 62.3 ms | 1.5 % |
| RB3 @ 640 | 26.5 ms | 28.4 ms | 7.2 % |
| **IQ-9075 @ 640** | 10.48 ms | 14.04 ms | **34.0 %** |

The gap scales inversely with the measurement. On the IQ-9075 at 640, 86 of 100
samples sit near 14 ms and the minimum came from a fast tail that occurred 14 %
of the time. **`DEVICE_FPS = 4.8` survived unchanged** — at 200 ms per inference
the gap is under 1 % — but that is luck, not diligence.

Toolchain: QAIRT v2.45.0.260326154327 · QNN Backend API 5.45.0 · QNN Core API
2.34.0 · AI Hub Workbench aihub-2026.08.14.0. Per-run job URLs in
`experiments/QUALCOMM_BENCHMARK.md`.

**The 100 % is the headline, not the FPS.** Every layer of an attention-centric
YOLOv12 executes on the Hexagon NPU, with nothing falling back to CPU.

---

## Coverage

At 20 m altitude, 60° FOV, `DRONE_SPEED_MS = 5.0`:

```
footprint  = 2 × 20 × tan(30°) = 23.09 m
crossing   = 23.09 / 5         = 4.62 s
```

| Config | Looks at each patch of ground |
|---|---|
| RB3 @ 960 | ~22 |
| IQ-9075 @ 960 | ~74 |
| RB3 @ 640 | ~163 |
| IQ-9075 @ 640 | ~329 |

**Compute is not the binding constraint.** At 22 looks, coverage is saturated;
the remaining hard problem is per-look recall.

### Why 960, with the cost named

To deliver ~22 looks on the RB3:

| | NPU duty cycle |
|---|---|
| 960 | ~100 % |
| 640 | ~13.6 % |

**960 costs ~7.4× the compute duty cycle for +4.7 points of recall.** The right
call for search-and-rescue — a missed survivor is unrecoverable, shorter
endurance is a mission-planning problem — but it is a priced trade, not a free
win.

Say *"compute duty cycle,"* not watts. AI Hub reports latency, not power.

---

## Open question

The NPU scales far worse with resolution than a GPU does:

| | 960 ÷ 640 time |
|---|---|
| Pixel count | 2.25× |
| Tesla T4 GPU | 2.62× |
| Attention's quadratic ceiling | 5.06× |
| IQ-9075 NPU (QCS9075) | **4.44×** |
| RB3 Gen 2 NPU (QCS6490) | **7.38×** |

Recomputed on medians, the IQ-9075 lands **inside** the 2.25–5.06× band where a
mix of quadratic attention and linear convolution belongs. The RB3 — the weaker
part — is still above it. That reads as attention accounting for the bulk on the
capable device, with the constrained one paying something extra, plausibly
memory pressure. **Two devices is not a trend, and this is inference from a
ratio rather than a measurement of where the time goes. Not established.**

Settle it by benchmarking `yolov8n` (pure convolution) at both sizes on the same
device. If v8n scales ~2.25× and v12s ~7.8×, attention is confirmed. If both
scale ~7×, it is memory and tiling.

---

## Compute budget — does it fit on the aircraft?

Measured 18 Sept 2026 by timing this repository's own modules over the demo
clip's 7,081 detections and `simulation/`'s 20×20 planner grid, then scaling
**8×** as a pessimistic allowance for ARM against the development machine.

| Stage | Time | Frequency |
|---|---:|---|
| **Detection @960 INT8** | **209.5 ms** | every frame *(measured on RB3 Gen 2)* |
| Localization (`backend/localize.py`), 23 survivors | 0.25 ms | every frame |
| Priority scoring (`backend/priority.py`), O(n²) | 1.57 ms | every frame |
| **Planner (`simulation/planners.py`), 400 cells + argmax** | **0.28 ms** | **once per `COMMIT_S = 20 s`** |

```
downstream work per frame   ~1.8 ms
detection per frame        209.5 ms
                           ─────────
downstream share              0.87 %
```

**Planner duty cycle: 0.0014 %.** Detection is the entire compute cost;
everything that makes the system *adaptive* rather than merely a detector is
free by comparison.

**What this does and does not establish.** It establishes that compute is not
the obstacle to running the planner onboard — that was the open question and it
is now closed. It does **not** establish that the integrated loop works: it has
never been assembled on hardware. Two detectors for RGB + thermal fusion
measured **2.4 FPS**, and sustained thermal and power draw remain unmeasured
(below).

---

## Not measured

State these as unmeasured wherever they appear.

| | Why it matters |
|---|---|
| **INT8 accuracy** | All device latencies are INT8; all accuracy figures are FP32. Never present them as one system. |
| **Raspberry Pi 4** | Different silicon, with no neural accelerator. The Qualcomm figures do not fill a Pi row. |
| **Power draw** | Duty cycle is a proxy, not a measurement. |
| **Ground-truth survivor count** | Demo clip shows 23 unique tracks; no hand count to check it against. |
| **Sustained thermal / power under load** | The 209.5 ms figure is a benchmark, not a 20-minute sortie. Throttling is plausible and untested. |
| **The integrated onboard loop** | Each stage is timed in isolation. Perception → planner → flight controller has only ever closed in simulation. |
| **Camera attitude during capture** | Every pin assumes a nadir camera. On a moving multirotor that is false, and it is the largest error term in localization — see below. |

Seven labelled gaps beside the measured numbers above is a stronger position
than a table with no gaps — a table with no gaps invites the question of which
entries were guessed. Say them before a judge finds them.

---

## The nadir assumption, quantified

`backend/localize.py` projects pixels to GPS assuming the camera points
straight down. A quadcopter translates **only** by tilting, so while the
aircraft is moving between search cells that assumption does not hold, and the
resulting error is a bearing error of `H · tan θ`:

| Airframe tilt | Ground centre shifts (H = 20 m) | Share of the 23.09 m footprint |
|---|---:|---:|
| 5° | 1.75 m | 7.6 % |
| 10° | 3.53 m | 15.3 % |
| **20°** | **7.28 m** | **31.5 %** |
| 30° | 11.55 m | 50.0 % |

**A 20° tilt moves every pin by 7.3 m — roughly half of `CLUSTER_RADIUS_M`
(15 m).** That is enough to merge two groups or split one, and group size is a
scored term in `backend/priority.py`. So this does not stop at the coordinate:
it propagates into the rescue order the dashboard displays.

Altitude error is negligible beside it. GSD is linear in H, so a 0.4 m
excursion is a 2 % scale error — 0.46 m across the entire frame. **Tilt is the
term worth engineering against; height hold is not.**

**Provenance.** The tilt angles and the airframe behaviour come from a
quadcopter PID study on Swift Pico in MuJoCo — eYRC Khoj-o-Drone Task 1,
September 2026, team eYRC#2802. That study measured a 1.525 kg airframe,
21.88 N maximum thrust, hover at **68.4 %** of maximum, **+4.54 m/s² climb
against −9.81 m/s² fall**, and **no aerodynamic damping at all**. It observed
altitude leaving its tolerance band precisely while pitch and roll were making
their large corrections, and put the thrust cost of tilting at `T·cos θ` —
6 % at 20°, 13 % at 30°, against a margin of only 32 % above hover.

That is a **different airframe in a different simulator**, so the angles are
the right order of magnitude rather than ARES's own numbers. The displacement
arithmetic above is exact for any airframe; only the choice of which tilt
angles are realistic is borrowed.

**What follows from it.** IMU fusion is not a checklist item on the roadmap —
it is worth about 7 m of localization error, and that is the honest reason to
build it. Two mitigations need no new sensor and belong in the flight plan:
hold attitude while observing and translate between observations, or tag each
frame with its tilt and drop detections above a threshold. The first costs
search time, the second costs coverage, and both remove the error.

**This does not correct the current demo.** Those pins come from stored
VisDrone and C2A footage whose true camera attitude is unknown, so the nadir
assumption is unverified for them as well. The honest statement is that the
assumption is undischarged in both directions — not that the footage is nadir
and only a real flight would differ.


---

## Where these numbers are wired

`DEVICE_FPS` is no longer `None`. The dashboard now reads the measured figure
through one constant, as designed:

| File | Value |
|---|---|
| `backend/config.py` | `DEVICE_FPS = 4.8`, `DEVICE_NAME = "Dragonwing RB3 Gen 2 (QCS6490)"` |
| `frontend/src/config.js` | same values, as the backend-offline fallback |
| `frontend/src/HeaderBar.jsx` | renders it on screen — required by CONVENTIONS.md once measured |
| `frontend/src/MissionParameters.jsx` | carries the provenance: which board, INT8, 100 % NPU, and that INT8 accuracy is separate and unmeasured |

**We publish the RB3 figure, not the IQ-9075's 16.1 FPS.** It is the slower of
the two boards and the drone-class one. Quoting the better of two measurements
is not reporting.

The `None` path is deliberately kept. It is still the honest state for any
device nobody has put a model on, and it is what the Pi row would render.

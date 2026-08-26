# Part 4 — Export, ONNX, and On-Device Benchmarking

This is the part of ARES that makes the phrase "on-device AI inference" true
rather than aspirational, and it is the claim a hardware-edition judge is most
likely to press on.

---

## 1. Why export at all

Your trained model is a `.pt` file — a PyTorch checkpoint. PyTorch is a *research*
framework: flexible, Python-dependent, and heavy. On a Raspberry Pi, installing
PyTorch is a slow, large, sometimes painful exercise, and running it is slower
than it needs to be.

**Export** converts the model into a format designed for deployment: a frozen
computation graph that a lightweight runtime can execute without Python's
research machinery.

The trade: you lose the ability to train or modify the model. You gain speed,
portability, and a much smaller install.

---

## 2. What ONNX is

**ONNX** — Open Neural Network Exchange — is an open standard for representing
neural networks. Think of it as a common file format: PyTorch, TensorFlow and
others can all *write* it, and many runtimes can *read* it.

An ONNX file contains:

- The **graph**: which operations run in what order (convolution → activation →
  attention → …)
- The **weights**: the trained numbers
- The **input/output shapes**

What it does *not* contain is any Python. That is the point.

### The export command

```bash
yolo export model=best.pt format=onnx imgsz=960 opset=12 simplify=True
```

| Argument | What it does |
|---|---|
| `format=onnx` | The target format |
| `imgsz=960` | **Bakes the input size into the graph.** Export at the size you will run at |
| `opset` | ONNX operator-set version. Higher supports more ops; lower is more portable |
| `simplify` | Runs `onnxslim` to fold redundant operations. Smaller and faster |

Or in Python:

```python
from ultralytics import YOLO
YOLO("best.pt").export(format="onnx", imgsz=960, simplify=True)
```

### The thing that was uncertain and turned out fine

YOLOv12 is attention-centric, and attention blocks — especially FlashAttention —
do not always export cleanly to ONNX. This was a genuine risk when you started,
because a model that will not export is a model that cannot be deployed, and it
would have forced a fall back to YOLOv8.

**It exported.** Worth knowing that you verified it rather than assumed it.

### `imgsz` at export time

Your detections were produced at **960**. The Pi benchmark must therefore also run
at 960, not 640.

This matters more than it sounds. 960² is **2.25×** the pixels of 640², so
inference is roughly 2.25× slower. Benchmarking at 640 and reporting that number
beside detections produced at 960 would be a real misrepresentation — the fast
number would describe a configuration you do not ship.

---

## 3. Runtimes

An ONNX file needs something to execute it. Which one depends on the hardware.

| Runtime | Best for | Notes |
|---|---|---|
| **ONNX Runtime** | Everything, CPU and GPU | Microsoft's. The general-purpose default |
| **NCNN** | ARM CPUs — phones, Raspberry Pi | Tencent's, hand-optimised for ARM. Often the fastest option on a Pi |
| **OpenVINO** | Intel CPUs, integrated GPUs | Intel's |
| **TensorRT** | NVIDIA GPUs, Jetson | NVIDIA's. Fastest on their hardware, unusable elsewhere |
| **CoreML** | Apple Silicon, iOS | Apple's |
| **TFLite** | Mobile, microcontrollers | Google's |

Ultralytics exports to all of these with a format flag.

### For a Raspberry Pi 4

The Pi 4 has a **Cortex-A72** CPU — ARM, four cores, no usable GPU for this, and
no neural accelerator.

**Try both ONNX Runtime and NCNN and measure.** NCNN is usually faster on ARM
because it is built specifically for it, but "usually" is not "measured", and the
whole point of this exercise is producing a real number.

```bash
yolo export model=best.pt format=ncnn imgsz=960
```

### The Python version trap you hit

```
ERROR: onnxruntime>=1.20 requires Python 3.10+
```

You were on Python 3.9. `ai/requirements.txt` now records the ceiling:

```
onnxruntime>=1.19          # 1.20+ requires Python 3.10; 1.19.2 is the ceiling on 3.9
```

A comment that saves the next person twenty minutes is worth writing.

### The Pi needs a 64-bit OS

Also recorded in `ai/requirements.txt`: `uname -m` must print `aarch64`. A 32-bit
Raspberry Pi OS will refuse or badly underperform. Flash the 64-bit image — this
is worth checking *before* the SD card arrives, not after.

---

## 4. How to benchmark honestly

`tools/benchmark.py` is twenty-eight lines and every one of them is about not
lying to yourself.

```python
# Warm up — never time these. The first calls include model load,
# memory allocation and cache warming.
for _ in range(5):
    model.predict(IMAGE, imgsz=IMGSZ, conf=0.18, max_det=1000, verbose=False)

times = []
for _ in range(30):
    t0 = time.perf_counter()
    r = model.predict(IMAGE, imgsz=IMGSZ, conf=0.18, max_det=1000, verbose=False)
    times.append((time.perf_counter() - t0) * 1000)

med = statistics.median(times)
```

### The four things it gets right

**1. Warm-up runs, discarded.** The first inference includes model loading, memory
allocation, cache warming and lazy initialisation. It can be five or ten times
slower than steady state. Timing it produces a number that describes nothing.

**2. Median, not mean.** A single OS scheduling hiccup adds a large outlier. The
mean absorbs it; the median ignores it. Both are printed so you can see whether
they diverge — if they do, something is interfering.

**3. Best and worst are printed.** A wide spread means thermal throttling, another
process competing, or an unstable environment. A benchmark with no variance
information is not a benchmark.

**4. The stage breakdown.** `r[0].speed` gives preprocess / inference /
postprocess in milliseconds separately.

That last one matters more than it looks. If postprocess dominates, the
bottleneck is **NMS**, not the network — and NMS cost scales with the number of
detections, which at `conf=0.18` and `max_det=1000` in a dense frame can be
substantial. That is an optimisation target completely different from "the model
is too big."

### Benchmark the *densest* frame

`tools/build_demo_clip.py` extracts the busiest frame of the clip specifically for
this:

```python
busiest, count = Counter(d["frame_id"] for d in detections).most_common(1)[0]
```

and saves it as `models/test_frame_dense.jpg`.

Benchmarking an empty frame measures the network alone. Benchmarking the densest
frame measures the network **plus** the NMS cost you will actually pay. A search
UAV's worst case is a crowd, and the worst case is the number worth reporting.

### Thermal throttling

A Pi 4 under sustained load heats up and **the firmware reduces clock speed to
protect the chip.** So a 30-run benchmark can start fast and end slow.

- Use active cooling (a fan or a heatsink case)
- Watch `vcgencmd measure_temp` during the run
- If best and worst diverge widely across the run, you are watching throttling

Report the **sustained** figure. A burst number that the device cannot hold for a
ten-minute flight is not the number a rescue operator would experience.

---

## 5. Coverage: why frame rate was never the constraint

**This section used to be titled "Why ~1 FPS is a good answer."** It was written
when the only target was a Raspberry Pi 4 and the expected figure was around one
frame per second, and its job was to defend that number.

It no longer has to. Section 6 records **4.8 FPS on a Dragonwing RB3 Gen 2 and
16.3 FPS on an IQ-9075**, both measured on real silicon, both with 100 % of the
network on the Hexagon NPU. The defensive framing is obsolete.

The underlying argument, though, is not — and it got *stronger*, because it is
what tells you the extra frames are surplus rather than necessary. Keep the
geometry; drop the apology.

### The footprint argument

At 20 m altitude with a 60° field of view, the camera sees:

```
footprint = 2 × 20 × tan(30°) = 23.09 metres of ground
```

A drone flying forward at speed *v* crosses its own footprint in `23.09 / v`
seconds. During that time, **the same patch of ground is visible in every frame
captured.**

At `DRONE_SPEED_MS = 5.0`, that is **4.6 seconds per crossing** — and every frame
captured in those 4.6 seconds is another look at the same patch of ground.

| Platform | Measured FPS | Looks at each patch |
|---|---|---|
| *(hypothetical 1 FPS)* | 1.0 | ~5 |
| RB3 Gen 2 @ 960 | 4.8 | **~22** |
| IQ-9075 @ 960 | 16.3 | **~75** |
| RB3 Gen 2 @ 640 | 37.7 | ~174 |
| IQ-9075 @ 640 | 95.4 | ~441 |

Even the pessimistic 1 FPS case gives a survivor five independent chances to be
detected. On the RB3 it is twenty-two. A missed detection in one frame is
recovered in the next, twenty-one times over.

> **"A search UAV does not need 30 FPS. It needs to not miss the ground."**

That sentence is still the whole argument, and the measurements changed which
half of it carries the weight. The interesting claim is no longer *"1 FPS is
enough."* It is:

> **"Compute stopped being the binding constraint. At 4.8 FPS every patch of
> ground is already seen ~22 times, so the remaining question is not how fast the
> model runs — it is whether the detector finds a half-buried person at all. That
> is a recall problem, and it is where we spent the effort."**

That reframe is worth more than the speed number by itself, because it tells a
judge you know which of your constraints actually binds.

### The number to quote, and where it comes from

`backend/config.py` is the authority: `DRONE_SPEED_MS = 5.0`. Derive the figure
every time rather than quoting a remembered one:

```
23.09 m footprint ÷ 5 m/s   = 4.6 s per crossing
4.6 s × 4.8 FPS  (RB3)      = ~22 consecutive frames of the same ground
4.6 s × 16.3 FPS (IQ-9075)  = ~75 consecutive frames of the same ground
```

An earlier draft flagged a conflict with `CLAUDE.md`, which once stated 7.7
seconds — implying 3 m/s. That line is gone from `CLAUDE.md`, so there is
nothing left to reconcile. The lesson stands regardless: **the pitch, the deck
and this handbook all compute from the one constant.** The moment three
documents each carry their own remembered number, one of them is wrong and
nobody knows which.

One caveat worth being precise about if a judge presses. `DRONE_SPEED_MS` is a
per-clip localization constant — the assumed track that spreads survivors along
a flight path on the map. A real search-speed specification is an operational
choice that would be set by mission planning, not by this file. On the
prototype they are the same number, and saying so is more honest than implying
the 5 m/s was chosen as a search doctrine.

---

## 6. The Qualcomm benchmark — the result that changed the story

Qualcomm authored the SIH problem statement. Qualcomm also runs **AI Hub**, a
free service that compiles your model and profiles it on **physically real
devices** in their lab. That combination is not a coincidence you should waste.

`tools/qualcomm_benchmark.py` runs the whole chain: quantize → compile → profile.

### The measurements

All runs: **YOLOv12s, INT8 weights + INT8 activations, QNN context binary.**

| | RB3 Gen 2 (QCS6490) | IQ-9075 EVK (QCS9075) |
|---|---|---|
| **960 latency** | 207.56 ms · **4.8 FPS** | 61.45 ms · **16.3 FPS** |
| **640 latency** | 26.54 ms · 37.7 FPS | 10.48 ms · 95.4 FPS |
| **960 → 640 ratio** | **7.82×** | **5.86×** |
| Peak memory (960 / 640) | 9.5 / 10.4 MB | 8.9 / 6.5 MB |
| Layers on NPU | 489 / 489 | 489 / 489 |
| **NPU coverage** | **100 %** | **100 %** |

**The 100 % is the headline, not the FPS.** A partially-mapped network falls back
to CPU for the unsupported layers, and those fallbacks dominate the latency. Every
one of 489 layers executing on the Hexagon NPU means an attention-centric YOLOv12
maps *completely* onto Qualcomm's accelerator — which is a claim about their
silicon that most submissions will not have measured.

Peak memory under 10 MB is the other quietly strong number. It is what makes
"this runs on the aircraft, not in a datacentre" a measurement rather than a
slogan.

### The scaling anomaly — an open question, not a finding

960 is **2.25×** the pixels of 640. Three platforms disagree sharply about what
that costs:

| Platform | 960 ÷ 640 time |
|---|---|
| Pixel count (the naive expectation) | 2.25× |
| Tesla T4 GPU | 2.62× |
| **IQ-9075 Hexagon NPU** | **5.86×** |
| **RB3 Gen 2 Hexagon NPU** | **7.82×** |

Near-linear on a GPU. Wildly superlinear on the NPU. That is a real result and
it is worth being disciplined about, because the last confident hardware
explanation offered in this project — *"attention doesn't map to Hexagon"* —
was wrong, and nearly went into a submission to Qualcomm.

**Hypothesis, clearly labelled:** YOLOv12 is attention-centric, and attention
cost scales with the *square* of spatial token count. 2.25× the tokens implies
5.06× the attention cost, while convolutions scale at 2.25×. A blend of the two
should land between 2.25× and 5.06×. The observed 5.86× and 7.82× sit **above**
that ceiling, so attention alone does not account for it. A memory-tiling effect
is the likely remainder — 960 activations exceeding on-chip SRAM and spilling to
DRAM. The inverted peak memory on the RB3 (10.4 MB at 640 against 9.5 MB at 960)
suggests the compiler chose different tiling strategies, which is consistent with
that story and is not proof of it.

**The experiment that would settle it.** `yolov8n.pt` is pure convolution with no
attention. Export it at both sizes and benchmark both on the RB3:

- v8n scales ~2.25× while v12s scales ~7.8× → **attention is the cause,
  measured.**
- v8n also scales ~7× → the cause is memory and tiling, independent of
  architecture.

Two exports and four AI Hub jobs converts a hypothesis into a controlled result.
Until someone runs it, this section says *"we measured this and do not yet know
why,"* which is a perfectly respectable thing to say and a much better one than a
confident wrong answer.

### Why calibration data matters

Quantization needs **calibration frames** — real images, run through the network,
so the quantizer can observe the actual range of every activation and choose
integer scales that cover it.

The script feeds 64 frames evenly spread across the clip, letterboxed exactly as
deployment letterboxes them:

```python
def letterbox(img, size):
    r = min(size / h, size / w)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    # calibration must see the same input distribution as deployment
```

Calibrate on differently-preprocessed images and you tune the quantizer for a
distribution you never actually feed it. The output still runs. It is just
quietly worse, in a way no error message tells you about.

---

## 7. Two failures worth more than the success

The benchmark did not work first time. Both failures taught something.

### Failure 1: a malformed file that four hypotheses missed

```
Tensors {'output0'} occur in value_info but also in model IO.
```

Four explanations were proposed for this: NPU operator limits, a quantization
requirement, an activation-size ceiling, and YOLOv12's attention blocks not
mapping to Hexagon.

**All four were wrong.** The ONNX spec says `graph.value_info` carries types for
tensors that are *neither* graph inputs nor outputs. Ultralytics' export left
`output0` in both places. ONNX Runtime tolerates the violation, which is why
local benchmarking never noticed; AI Hub's compiler validates strictly.

`tools/fix_onnx_io.py` removes the duplicate entries. It changes **zero
operators and zero weights.**

The near-miss is the lesson. The most plausible-sounding hypothesis —
*"attention doesn't map well to the Hexagon NPU"* — was on its way into the
submission as a finding. It would have been a **false claim about Qualcomm's own
hardware, in a document submitted to Qualcomm**, and the eventual 100 % NPU
coverage is its direct refutation.

> **A confident explanation that fits the symptom is not a diagnosis. Read the
> spec.**

### Failure 2: float32 I/O on an integer-only NPU

```
Tensor 'images' has a floating-point type which is not supported
by the targeted device
```

The Hexagon HTP is **integer-only**. Not "faster with integers" — it has no
floating-point path at all. Feeding it FP32 inputs is not a performance question,
it is unsupported. Hence `--quantize_io` whenever the model is quantized.

### And a bug in the harness itself

The first version of `qualcomm_benchmark.py` queued a profile job against a model
that had failed to compile — and reported the resulting nonsense. Every stage now
blocks and checks:

```python
def check(job, label):
    status = job.wait()
    ok = getattr(status, "success", None)
    if ok is None:
        ok = str(getattr(status, "state", status)).upper() in {"SUCCESS", "COMPLETED"}
```

**A benchmark that cannot fail loudly is a benchmark you cannot trust.**

---

## 8. Accuracy: what is measured and what is not

Speed without accuracy is meaningless — an infinitely fast model that detects
nothing has excellent latency.

### FP32, measured

Combined C2A + VisDrone validation split, 2 591 images, 86 092 person instances.
The **same checkpoint** evaluated at both resolutions, so the only variable is
`imgsz`:

| Metric | 640 | **960 (shipped)** | Δ |
|---|---|---|---|
| Precision | 0.854 | **0.864** | +0.011 |
| Recall | 0.727 | **0.774** | **+0.047** |
| mAP50 | 0.783 | **0.833** | +0.049 |
| mAP50-95 | 0.511 | **0.577** | **+0.066** |
| Inference (T4) | 10.0 ms | 26.2 ms | 2.62× |

Recall gains most — the expected signature of giving a small-object detector
more pixels. Note also that **2.25× the pixels costs 2.62× the time**: attention
scales slightly worse than linearly in pixel count.

### Decomposing the improvement

An earlier figure existed from epoch 44 at 640 (mAP50-95 **0.494**). Three
measurements let you separate two variables that would otherwise be confounded:

```
mAP50-95   0.494   →   0.511   →   0.577
           ep44         final       final
           @640         @640        @960
                     └───────┘  └──────────┘
                     training     resolution
                      +0.017        +0.066
```

**Resolution accounts for ~80 % of the gain; finishing training ~20 %.** One
extra validation run bought that decomposition. Without the middle measurement
you could only say "it got better" and not say why.

### Why not run at 640 and take the speed?

The obvious challenge: 640 is far faster, and Section 5 already shows ~22 looks
per patch at 960. Why not bank the speed?

| | 960 | 640 |
|---|---|---|
| RB3 Gen 2 | 4.8 FPS → ~22 looks | 37.7 FPS → **~174 looks** |
| IQ-9075 | 16.3 FPS → ~75 looks | 95.4 FPS → **~441 looks** |
| Recall per look | **0.774** | 0.727 |

174 looks at one patch of ground is absurd, and the correlated-failure argument
bites hardest exactly there. Consecutive frames of the same person, at the same
altitude, seconds apart, fail in *correlated* ways: a target too small to
resolve at 640 is still too small in the next frame. Small changes in viewing
angle and occlusion recover some, but nowhere near what 174 independent trials
would. You would be spending compute to re-fail the same detection 152 more
times.

> **Extra looks have sharply diminishing returns because failures correlate.
> Extra resolution raises the ceiling on every look. Past the point where
> coverage saturates, resolution is the better purchase — and 22 looks is well
> past it.**

### But name the cost honestly

To deliver ~22 looks per patch on the RB3:

| | NPU duty cycle |
|---|---|
| 960 | 4.8 × 207.56 ms ≈ **996 ms/s → ~100 %** |
| 640 | 4.8 × 26.54 ms ≈ **127 ms/s → ~13 %** |

**960 costs roughly 7.8× the compute duty cycle for +4.7 points of recall.** On a
battery-limited aircraft, energy is flight time and flight time is search area.

The verdict stands — for search-and-rescue, take the recall, because a missed
survivor is unrecoverable while shorter endurance is a mission-planning problem.
But state it as an argued trade with a number attached, not as a free win. The
version with the cost named is the more credible one.

Say **"compute duty cycle,"** not watts: AI Hub reports latency, not power.
Duty cycle is a reasonable first-order proxy only if the NPU draws similar power
while active at both sizes — plausible, and unverified here.

### INT8, not measured

The benchmarked model is INT8. **Its accuracy is not the table above.**
Quantization costs something; how much is an empirical question nobody has
answered for this model.

So the rule is the same one that governs `DEVICE_FPS`:

> Quote 0.833 mAP50 as the **FP32** figure and tag the INT8 accuracy **"not yet
> measured."**

Pairing an FP32 accuracy with an INT8 latency and presenting them as one system
is the kind of quiet misstatement that a careful judge catches and that costs far
more than the missing number would have.

### The validation trap that nearly landed

A validation run was performed against `yolo12s.pt` — the **stock COCO
checkpoint**, auto-downloaded by Ultralytics because the path pointed at a file
that did not exist. It reported mAP50 **0.276**.

Three signals caught it:

| Signal | Stock | Trained |
|---|---|---|
| `names` | 80 COCO classes | `{0: 'human'}` |
| Parameters | 9 261 840 | 9 231 267 |
| `nt_per_class` | length 80 | length 1 |

The parameter gap is exactly **30 573**, which is precisely
`3 × 129 × (80 − 1)` — the three `Conv2d(128, nc, 1)` layers in the detection
head. Arithmetic, not intuition.

> **Before trusting any validation number, print `model.names`.** One line. It
> distinguishes "our model scores 0.833" from "our model scores 0.276," and only
> one of those is true.

---

## 9. `DEVICE_FPS`, and the Pi checklist

```python
DEVICE_FPS: Optional[float] = None
DEVICE_NAME: str = "Raspberry Pi 4 Model B"
```

`None` renders as a dash and the words **"not yet measured"**. That is still the
honest state for the *Pi* — the SD card is on order and nobody has run it.

The Qualcomm numbers do not fill this in, because they are a different device.
Two measured platforms and one unmeasured one is a perfectly respectable state to
present; silently reusing an IQ-9075 figure under a "Raspberry Pi 4" label is
not.

When a real Pi figure arrives, you set the one constant and **nothing else
changes** — the panel picks it up through `/api/config` and re-tags the row
"measured". One constant, one edit, the whole dashboard follows. Worth pointing
out if a judge asks about the architecture.

### The interim CPU number

Recorded in `experiments/MODEL_SELECTION.md` from a Mac CPU run. **Not** a Pi
number and it must never be presented as one — but it holds a prediction that was
measured and overturned.

The expectation was that YOLOv12's attention would be *disproportionately* worse
on CPU than GPU, attention being memory-bandwidth hungry. The measurement said
otherwise: CPU ratio 2.18× against GPU 3.14×. Attention was **relatively better**
on CPU than predicted — and, as Section 6 later showed, mapped 100 % onto the
Hexagon NPU as well.

Two independent measurements, both contradicting the same intuition. Keep
predictions that get overturned; they are what separates a project that measured
things from one that assumed them.

### The checklist

1. **Flash 64-bit Raspberry Pi OS.** Verify with `uname -m` → `aarch64`.
2. **Attach active cooling.** A fan, or at minimum a heatsink case.
3. **Copy over** `best.pt`, the ONNX export, and `models/test_frame_dense.jpg`.
4. **Install** `ai/requirements.txt`, minding the `onnxruntime<1.20` ceiling if
   Python is 3.9.
5. **Benchmark at `imgsz=960`**, not 640. This is the one most likely to be got
   wrong, and it is the one that would misrepresent your system.
6. **Run both models** — YOLOv12s and YOLOv8n — so you can state the trade rather
   than assert it.
7. **Try both runtimes** — ONNX Runtime and NCNN.
8. **Watch the temperature** with `vcgencmd measure_temp` and report the sustained
   figure.
9. **Record the stage breakdown.** If postprocess dominates, say so — it is a
   different and more interesting finding than "the model is slow."
10. **Put the number in `backend/config.py`.** Nothing else.

```bash
python tools/benchmark.py models/yolov12s.pt 960 models/test_frame_dense.jpg
python tools/benchmark.py models/yolov8n.pt  960 models/test_frame_dense.jpg
```

---

## 10. What you would improve

**1. Measure the INT8 accuracy.** The single largest gap in the story. You have
an INT8 latency and an FP32 accuracy and no honest way to state them as one
system until this exists.

**2. Frame skipping as an explicit power policy.** At ~22 looks per patch on the
RB3, processing every frame is *waste*, not thoroughness. Deliberately running one
frame in four to buy flight endurance is a designed choice justified by the
footprint arithmetic — and on a battery-limited aircraft, endurance is search
area. This became interesting only *because* the device turned out to be fast.

**3. Resolution scheduling.** Run low-resolution continuously; re-run the same
frame at 960 when something is detected. Cheap most of the time, accurate when it
matters.

**4. The 640-vs-960 comparison, on device.** You have accuracy at both. Latency at
both would let you state the trade in full: *"960 costs us X ms and buys us
+0.057 recall."* That is a defensible engineering decision rather than a
preference.

**5. Benchmark the Pi anyway.** Not because it is the best platform, but because
"commodity hardware and Qualcomm silicon, here are both" is a stronger position
than either alone.

**6. Accelerators as roadmap, not claim.** Coral TPU, Hailo, Jetson Orin. Each
would transform throughput, and each changes "on-device inference on commodity
hardware" into "…with an accelerator" — a different and slightly weaker claim.
Worth knowing, worth mentioning, worth not overstating.

---

## What to take from this part

- Export converts a research checkpoint into something a lightweight runtime can
  execute. YOLOv12's attention blocks **do** export to ONNX, and **do** map 100 %
  onto the Hexagon NPU — both verified, neither assumed.
- Benchmark with warm-up runs discarded, take the median, report the spread, and
  use the **densest** frame.
- Benchmark at **960**, because that is what your detections were produced at.
- **Measured at 960: 4.8 FPS on RB3 Gen 2, 16.3 FPS on IQ-9075.** At 640: 37.7
  and 95.4 FPS. All four runs **489/489 layers on the NPU**, all ≤10.4 MB peak.
- **The NPU scales far worse with resolution than a GPU does** — 5.86–7.82× for
  2.25× the pixels, against 2.62× on a T4. Cause not yet established; the v8n
  control experiment would settle it.
- **960 costs ~7.8× the compute duty cycle for +4.7 points of recall.** Still the
  right call for SAR, but state it as a priced trade, not a free win.
- **Compute is no longer the binding constraint.** At 4.8 FPS every patch of
  ground is already seen ~22 times. The remaining hard problem is recall, not
  throughput — and saying so shows you know which constraint binds.
- Derive **4.6 s per crossing** from `DRONE_SPEED_MS = 5.0` every time. Three
  documents each carrying a remembered number means one is wrong.
- **FP32 accuracy at 960: mAP50 0.833, mAP50-95 0.577.** INT8 accuracy is **not
  measured** — never pair an FP32 accuracy with an INT8 latency as one system.
- `DEVICE_FPS = None` still renders "not yet measured" for the *Pi*. Qualcomm
  numbers do not fill in a Raspberry Pi row.
- **Print `model.names` before trusting any validation number.** One line
  separates 0.833 from 0.276.
- A confident explanation that fits the symptom is not a diagnosis. Four
  plausible hypotheses were all wrong; the answer was in the ONNX spec.

**Next:** Part 5 — the backend, from "what is an API" through every function in
every file.

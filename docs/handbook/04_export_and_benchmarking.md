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

## 5. Why ~1 FPS is a good answer

This is the most important argument in this part, and it is one that turns an
apparent weakness into evidence of engineering judgment.

A judge sees "1 FPS" and thinks *that's terrible, video is 30 FPS.* You need the
answer ready, and it is a genuinely strong one.

### The footprint argument

At 20 m altitude with a 60° field of view, the camera sees:

```
footprint = 2 × 20 × tan(30°) = 23.09 metres of ground
```

A drone flying forward at speed *v* crosses its own footprint in `23.09 / v`
seconds. During that time, **the same patch of ground is visible in every frame
captured.**

| Ground speed | Time to cross footprint | Frames of the same ground at 1 FPS |
|---|---|---|
| 3 m/s | 7.7 s | ~8 |
| 5 m/s | 4.6 s | ~5 |

So even at 1 FPS, a survivor gets **five to eight independent chances** to be
detected as the drone passes over them. A missed detection in one frame is
recovered in the next.

> **"A search UAV does not need 30 FPS. It needs to not miss the ground."**

That sentence is the whole argument. Thirty FPS would give you thirty looks at
the same patch, twenty-nine of which are redundant, at thirty times the power
budget on a battery-limited aircraft.

### The number to quote, and where it comes from

`backend/config.py` is the authority: `DRONE_SPEED_MS = 5.0`. So the figure to
use on stage is **4.6 seconds and five or more looks**, not eight.

An earlier draft of this handbook flagged a conflict with `CLAUDE.md`, which
used to state 7.7 seconds — implying 3 m/s. That line is no longer in
`CLAUDE.md`, so there is nothing left to reconcile in the repo. What matters is
that the pitch, the deck and this handbook all derive the figure from the one
constant rather than quoting a remembered number:

```
23.09 m footprint ÷ 5 m/s = 4.6 s per crossing
4.6 s at 1 FPS = ~5 consecutive frames of the same ground
```

One caveat worth being precise about if a judge presses. `DRONE_SPEED_MS` is a
per-clip localization constant — the assumed track that spreads survivors along
a flight path on the map. A real search-speed specification is an operational
choice that would be set by mission planning, not by this file. On the
prototype they are the same number, and saying so is more honest than implying
the 5 m/s was chosen as a search doctrine.

### The honest framing

> "We measured it on the target device and it is [X] FPS at 960 pixels. That
> sounds low next to video frame rates, and it is exactly what you would expect
> from a 9-million-parameter attention model on a Cortex-A72 with no accelerator.
> It is also enough: at our search altitude the aircraft takes about five seconds
> to cross its own camera footprint, so every patch of ground is seen in several
> consecutive frames. We would rather report the real number than a burst figure
> the device can't sustain."

**That is a better answer than a fast number, because it demonstrates you
understand your own system's requirements.**

---

## 6. Why `DEVICE_FPS` is `None`

```python
DEVICE_FPS: Optional[float] = None
DEVICE_NAME: str = "Raspberry Pi 4 Model B"
```

Nobody has run the benchmark yet — your SD card is on order.

`None` means exactly that. The dashboard renders a dash and the words **"not yet
measured"**, and the mission-parameters panel tags the row accordingly instead of
calling it measured.

The config comment says it best:

> An invented FPS figure is the same failure as a hand-authored detection, and
> this is the one number a judge is most likely to press on — a Raspberry Pi 4
> running a YOLO model is exactly where a prototype is expected to be slow.

When the real figure arrives, you set it in `backend/config.py` and **nothing
else changes.** The panel picks it up through `/api/config` and re-tags the row
"measured". No frontend edit.

That design — one constant, one edit, the whole dashboard follows — is worth
pointing out if a judge asks about the architecture.

### The interim number you do have

You benchmarked on Mac CPU, recorded in `experiments/MODEL_SELECTION.md`. That is
**not** a Pi number and must not be presented as one, but it is useful for a
comparison you got wrong and then measured:

The prediction was that YOLOv12's attention would be disproportionately worse on
CPU than on GPU, because attention is memory-bandwidth heavy and CPUs have less of
it. **The measurement said otherwise** — CPU ratio 2.18× against GPU 3.14×.
Attention was *relatively better* on CPU than expected.

Predictions that get measured and overturned are worth keeping. They are what
separates a project that measured things from a project that assumed them.

---

## 7. Your benchmark checklist for when the SD card arrives

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

## 8. What you would improve

**1. Quantisation.** INT8 quantisation converts weights from 32-bit floats to
8-bit integers — roughly 4× smaller and substantially faster on CPU, for a small
accuracy cost. The standard next step for edge deployment, and the single largest
speed win available to you.

**2. A Coral TPU or Hailo accelerator.** A USB or HAT accelerator would transform
the throughput. It also changes "on-device inference on commodity hardware" into
"on-device inference with an accelerator", which is a different and slightly
weaker claim. Worth knowing, worth mentioning as roadmap.

**3. Jetson Nano / Orin Nano.** A GPU-equipped edge board with TensorRT support.
Faster, more expensive, more power.

**4. Frame skipping as an explicit policy.** Rather than running as fast as
possible, deliberately process one frame every *N* to hit a target power budget.
Given the footprint argument, this costs nothing in coverage and is a *designed*
choice rather than a limitation.

**5. Resolution scheduling.** Run at low resolution continuously, and re-run the
same frame at high resolution when something is detected. Cheap most of the time,
accurate when it matters.

---

## What to take from this part

- Export converts a research checkpoint into something a lightweight runtime can
  execute. YOLOv12's attention blocks **do** export to ONNX — verified, not
  assumed.
- Benchmark with warm-up runs discarded, take the median, report the spread, and
  use the **densest** frame.
- Benchmark at **960**, because that is what your detections were produced at.
- **~1 FPS is defensible**: the aircraft takes several seconds to cross its own
  footprint, so every patch of ground is seen in several consecutive frames.
- Quote **4.6 s and ~5 looks**, derived from `DRONE_SPEED_MS = 5.0`. Never a remembered number.
- `DEVICE_FPS = None` renders "not yet measured". That is the honest state and it
  becomes a real number with a one-line edit.

**Next:** Part 5 — the backend, from "what is an API" through every function in
every file.

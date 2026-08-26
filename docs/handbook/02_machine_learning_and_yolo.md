# Part 2 — Machine Learning and YOLO, From Zero

This part assumes you know nothing about neural networks. By the end you should
be able to read your own training log line by line and explain every number in
it.

---

## 1. What a detector actually does

### The task

**Image classification** answers "what is in this picture?" — one label for the
whole image. *Cat.*

**Object detection** answers "what is in this picture, and where?" — a list of
boxes, each with a label and a confidence. *Person at (412, 88)–(437, 140),
0.87 confident. Person at (601, 210)–(628, 265), 0.64 confident.*

ARES needs detection, obviously. "There are people in this frame" is useless;
"there is a person at these coordinates" is actionable.

### The bounding box

A box is four numbers. Your contract uses the **xyxy** convention:

```
bbox = [x1, y1, x2, y2]
        │   │   │   └── bottom-right y
        │   │   └────── bottom-right x
        │   └────────── top-left y
        └────────────── top-left x
```

There are other conventions — **xywh** (top-left corner plus width and height)
and **cxcywh** (centre plus width and height, which is what YOLO uses
internally). Ultralytics gives you all three; `b.xyxy[0]` in your tools is asking
for the corner form.

**Image coordinates start at the top-left and y grows downward.** This is a
computer graphics convention and it is the opposite of a maths textbook. It
causes a specific bug in Part 6, so remember it.

### What "confidence" means

A number from 0 to 1 that the model attaches to each box. Loosely: *how sure am I
that this is a person and that this box is right.*

It is **not** a probability in the strict sense. A model that says 0.8 is not
correct exactly 80% of the time — modern networks are usually overconfident. What
it reliably is, is an **ordering**: a 0.8 detection is more likely to be real
than a 0.3 detection from the same model. That ordering is what you use it for,
both in the confidence threshold and in your priority score.

---

## 2. How a neural network detector works

You do not need the maths to defend this project, but you need the shape of it.

### The intuition

A neural network is a stack of layers. Each layer takes numbers in, multiplies
them by a big grid of adjustable values called **weights**, and passes the result
on. Early layers in a vision network learn to respond to simple things — edges,
corners, patches of colour. Later layers combine those into more complex things —
textures, then shapes, then "this pattern of shapes tends to be a person."

Nobody programmed "person" in. The network was shown many labelled examples and
the weights were adjusted until it got them right. That adjustment process is
**training**, and the weights it produces are what a `.pt` file contains.

### One-stage vs two-stage

There are two families of detector.

**Two-stage** (R-CNN, Fast R-CNN, Faster R-CNN): first propose regions that might
contain something, then classify each region. More accurate historically, slower,
because it does the work twice.

**One-stage** (YOLO, SSD, RetinaNet): look at the whole image once and predict
boxes and classes directly. Faster, and now roughly as accurate.

**YOLO stands for "You Only Look Once"** — that name *is* the architectural
claim. It is the one-stage family's founding idea.

For ARES this is not a close call. The model has to run on a Raspberry Pi. A
two-stage detector was never in the running.

### How YOLO predicts

Conceptually, YOLO divides the image into a grid and each grid cell is
responsible for predicting objects whose centre falls inside it. For each cell it
predicts box coordinates, an objectness score, and class probabilities — all in
one forward pass.

Older YOLO versions used **anchor boxes**: pre-defined box shapes that the model
adjusted rather than predicting from scratch. Modern versions (v8 onward) are
**anchor-free** — they predict box dimensions directly. Fewer hyperparameters to
get wrong.

### What YOLOv12 changed

YOLO up to v11 was almost entirely **convolutional** — an architecture that
processes local neighbourhoods of pixels. YOLOv12 is **attention-centric**, which
means it borrows the mechanism that made transformers work in language models.

Attention lets a position in the image consider *other, distant* positions when
deciding what it is looking at. The problem is that classic attention compares
every position to every other position, which costs time proportional to the
square of the number of positions — far too slow for real-time detection.

YOLOv12's contributions, from the Ultralytics documentation:

- **Area attention.** Instead of whole-image attention, the feature map is split into
  *l* equal regions (default 4), horizontally or vertically. You get a large
  receptive field without the quadratic cost.
- **R-ELAN** (Residual Efficient Layer Aggregation Networks). A redesigned feature
  aggregation block with block-level residual connections and scaling.
- **FlashAttention.** A memory-efficient attention implementation that reduces
  memory-bandwidth overhead.
- **No positional encoding.** Removed for a cleaner design, with a 7×7 separable
  convolution — the "position perceiver" — implicitly encoding position instead.
- **Adjusted MLP ratios**, from the standard 4 down to 1.2 or 2, rebalancing
  compute between attention and feed-forward parts.

The published COCO numbers:

| Model | mAP<sup>val</sup> 50-95 | T4 TensorRT speed | Parameters |
|---|---|---|---|
| YOLO12n | 40.6 | 1.64 ms | 2.6 M |
| **YOLO12s** | **48.0** | **2.61 ms** | **9.3 M** |
| YOLO12m | 52.5 | 4.86 ms | 20.2 M |
| YOLO12l | 53.7 | 6.77 ms | 26.4 M |
| YOLO12x | 55.2 | 11.79 ms | 59.1 M |

**Why this matters for your pitch:** YOLOv12 trades some raw speed for accuracy
compared to v11. On a Raspberry Pi that trade is worth interrogating, and it is
exactly the kind of thing a good judge will ask about. You have a real answer,
in Part 4.

### The size suffixes

`n`, `s`, `m`, `l`, `x` — nano, small, medium, large, extra-large. Same
architecture, scaled. More parameters means more accuracy and slower inference.

**You chose `s`.** The reasoning: `n` (2.6 M params) loses too much accuracy on
small aerial targets, where every pixel of signal counts. `m` and up are too slow
for a Pi 4. `s` at 9.3 M parameters is the point where an edge device is still
plausible and small-object accuracy is still acceptable.

---

## 3. Ultralytics — the library

**Ultralytics** is the Python package that implements YOLOv8, v11, v12 and
friends. It is the reason your training is five lines instead of five hundred.

```python
from ultralytics import YOLO

model = YOLO("yolov12s.pt")          # load pretrained weights
model.train(data="data.yaml", epochs=100, imgsz=640)
model.val()                          # measure on the validation set
model.predict(source="clip.mp4")     # run detection
model.track(source="clip.mp4")       # run detection + tracking
model.export(format="onnx")          # convert for deployment
```

Six methods cover essentially everything you did.

**Why Ultralytics rather than raw PyTorch:** it bundles training loops, data
loading, augmentation, metrics, checkpointing, export and tracking. Writing those
yourself is months of work and every one is a place to introduce a bug you cannot
see. The cost is that a lot happens implicitly — which is exactly why the rest of
this part exists.

**Version pinning matters.** You hit this: a Colab session resumed with 8.4.120
while the checkpoint was written by 8.4.126, and the run fell back to `coco8.yaml`
and rebuilt the model with 80 classes instead of 1. The error was
`ValueError: loaded state dict has a different number of parameter groups`. Pin
your version. `ai/requirements.txt` does: `ultralytics>=8.4.126`.

---

## 4. Training vocabulary

Every term you will see in a training log.

### Dataset splits

| Split | Purpose | Does the model learn from it? |
|---|---|---|
| **Train** | The model adjusts its weights on this | Yes |
| **Validation** | Measured after each epoch to check progress | No |
| **Test** | Held back for a final honest measurement | No |

The split exists because a model can **memorise**. Score it on data it trained on
and you learn nothing about whether it will work on a new photo.

### Epoch, batch, iteration

- **Batch** — a group of images processed together before the weights update.
  Yours was probably 16 or 32. Bigger batches are more stable but need more GPU
  memory.
- **Iteration** (or step) — one batch processed, one weight update.
- **Epoch** — one complete pass through the training set.

If you have 8,000 training images and a batch size of 16, that is 500 iterations
per epoch. **You trained for 100 epochs**, meaning the model saw every image 100
times.

### Loss

A number measuring how wrong the model currently is. Training is the process of
adjusting weights to make it smaller. Detection has three loss components, and
Ultralytics prints all three:

| Loss | What it measures |
|---|---|
| `box_loss` | How far predicted box coordinates are from the true ones |
| `cls_loss` | How wrong the class predictions are |
| `dfl_loss` | Distribution Focal Loss — refines box edge precision |

**What to look for:** all three trending down, with validation loss tracking
training loss. If training loss keeps falling while validation loss starts
*rising*, that is **overfitting** — the model is memorising rather than
generalising.

### Learning rate

How big a step to take when adjusting weights. Too high and training is unstable;
too low and it takes forever or gets stuck. Ultralytics schedules this for you —
typically warming up, then decaying toward the end.

**This is why the last epochs matter.** By epoch 90 the learning rate is small
and the model is making fine adjustments. It is where the last point or two of
mAP usually comes from. You stopped at 44 and did not get those — Part 9 covers
whether that mattered.

### Optimizer

The algorithm that decides how to change the weights given the loss. **SGD** and
**AdamW** are the common choices; Ultralytics picks sensibly by default.

### Augmentation

Randomly modifying training images so the model sees more variety than you
actually collected: flips, rotations, colour shifts, scaling, and **mosaic**
(stitching four images into one, which is especially good for small-object
detection because it forces the model to handle varied scales).

Ultralytics does this automatically. It is a large part of why training on a few
thousand images works at all.

### Transfer learning and pretrained weights

You did not start from random weights. `yolov12s.pt` ships pretrained on **COCO**
— 80 classes, 118,000 images, including a `person` class.

That model already knows edges, textures, limbs, and roughly what a human looks
like. **Fine-tuning** adjusts that knowledge toward your specific problem —
people seen from directly above, small, in rubble.

Starting from COCO instead of scratch is the difference between needing thousands
of images and needing millions.

### Checkpoints: `best.pt` vs `last.pt`

Ultralytics saves two files continuously:

- `last.pt` — the most recent epoch. Use this to **resume** an interrupted run.
- `best.pt` — the epoch with the best validation score so far. Use this to
  **deploy**.

They are often not the same epoch, and `best.pt` is nearly always what you want.

---

## 5. Your datasets

### C2A

*Combination to Attention* — a dataset of **people in disaster scenes**, built by
compositing human figures onto disaster imagery. Purpose-built for exactly your
problem: survivors in rubble, flood, collapsed structures.

### VisDrone

A large UAV benchmark: real drone footage, dense urban scenes, many small
objects, multiple object categories. It contributes the **aerial viewpoint** and
realistic small-target scale.

### Why you combined them rather than keeping them separate

C2A gives you *disaster context* but its imagery is composited. VisDrone gives
you *real aerial capture* but its people are ordinary pedestrians, not survivors.

Neither alone is your deployment distribution. Together they span it. C2A's own
paper confirmed that combining beat keeping them separate — which is the kind of
citation worth having ready when a judge asks why.

### Why one `person` class

Both datasets have multiple categories. You collapsed everything human into a
single `person` class.

Reasons:

1. **The task doesn't need it.** ARES counts and locates people. Distinguishing
   pedestrian from cyclist adds nothing a rescue coordinator can use.
2. **More data per class.** Merging categories means every human example trains
   the same class. With a small dataset that matters a lot.
3. **Fewer failure modes.** A model that confuses two person-like classes produces
   a confusing count. One class cannot.

### `data.yaml`

The file that tells Ultralytics where everything is:

```yaml
path: /content/datasets/combined
train: images/train
val: images/val
nc: 1                 # number of classes
names: ['person']
```

**`nc` is the thing that broke your Colab resume.** When the dataset wasn't
re-extracted, Ultralytics fell back to `coco8.yaml` (`nc: 80`), rebuilt the model
with 80 output channels, and could not load a checkpoint shaped for 1.

---

## 6. Metrics — the part that actually matters

This section is the one to read twice. Every number a judge will ask about is
here.

### The four outcomes

For any detection the model makes, compared against the ground truth:

| Outcome | Meaning |
|---|---|
| **True Positive (TP)** | Model found a real person, box is good enough |
| **False Positive (FP)** | Model reported a person where there is none |
| **False Negative (FN)** | A real person the model missed entirely |
| True Negative | Correctly reported nothing. Meaningless in detection — there are infinitely many places without a person |

### IoU — how "box is good enough" is decided

**Intersection over Union.** Take the predicted box and the true box:

```
IoU = area of overlap / area of union
```

- `IoU = 1.0` — perfect overlap
- `IoU = 0.5` — the boxes share half their combined area
- `IoU = 0.0` — no overlap at all

A detection counts as a TP if its IoU with a true box exceeds a threshold,
conventionally **0.5**.

### Precision

> Of everything the model *said* was a person, what fraction really was?

```
Precision = TP / (TP + FP)
```

High precision = few false alarms. **Your model: 0.864** at 960 px. About 86 % of
its detections are real people.

### Recall

> Of all the people that were actually there, what fraction did the model find?

```
Recall = TP / (TP + FN)
```

High recall = few misses. **Your model: 0.774** at 960 px. It finds about 77 % of
the people present — and **0.824** at the operating threshold of 0.18, which is
the number that actually matters, because 0.18 is what ships.

### The trade-off — and the core argument of this project

Precision and recall move in opposite directions as you change the confidence
threshold.

- **Raise the threshold** → only very confident detections survive → precision
  rises, recall falls. Fewer false alarms, more missed people.
- **Lower the threshold** → marginal detections are kept → recall rises, precision
  falls. More false alarms, fewer missed people.

Most detection systems default to `conf=0.5` and balance the two.

**Search and rescue is not a balanced problem.**

> A false alarm costs a rescuer thirty seconds of walking.
> A missed survivor cannot be recovered.

The costs are wildly asymmetric, so the threshold should be too. This is why
`CONFIDENCE_THRESHOLD = 0.18` and why the dashboard labels it
**"Detection Mode: High Recall"** rather than hiding it.

The measured effect on your model:

Measured at 960 px on the combined C2A + VisDrone val split (2,591 images,
86,092 instances), read off the PR curve:

| Threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.37 — F1-optimal | 0.864 | 0.775 | **0.817** |
| **0.18 — shipped** | 0.752 | **0.824** | 0.786 |

You give up **11 points of precision** and buy **4.9 points of recall**. Over
86,092 instances:

```
conf 0.37    TP 66,721    FP 10,502
conf 0.18    TP 70,940    FP 23,395
             ─────────    ─────────
             +4,219       +12,893
```

**About 3 extra false alarms per additional survivor found.** That ratio is the
single best thing you can say about this project's engineering judgment, because
a judge can evaluate it immediately: an operator dismisses a false box in a
second, and a missed survivor is not recoverable.

Note the comparison is against the **F1-optimal 0.37**, not the library's 0.5
default. Comparing to the optimum is the harder and more honest test — it shows
you left the best-balanced point on purpose, not that you beat an arbitrary
default.

### The PR curve

Sweep the confidence threshold from 0 to 1, plot precision against recall at each
point, and you get the **precision-recall curve**. Ultralytics saves it as
`PR_curve.png` in your validation run directory.

**This is the plot you used to choose 0.18**, and it is worth putting in the
deck. It shows the choice was read off a measurement rather than guessed.

### Average Precision and mAP

**AP** (Average Precision) is the area under the PR curve for one class — a single
number summarising performance across all thresholds. Higher is better, 1.0 is
perfect.

**mAP** (mean Average Precision) averages AP across classes. You have one class,
so mAP = AP.

Two variants get reported, and the difference matters:

| Metric | How it is computed | Yours |
|---|---|---|
| **mAP50** | AP at IoU threshold 0.5 only | **0.833** |
| **mAP50-95** | AP averaged over IoU 0.50, 0.55, … 0.95 | **0.577** |

**mAP50** asks "did you find the person, roughly?" — a loose box still counts.

**mAP50-95** asks "did you find the person *and* draw the box precisely?" — it
averages over increasingly strict overlap requirements, so it punishes sloppy
boxes hard.

mAP50-95 is always much lower. That is normal and expected, not a problem.

### Reading your numbers honestly

Measured on the combined C2A + VisDrone val split — 2,591 images, 86,092
instances. The **same checkpoint** at both sizes, so the only variable is `imgsz`:

| | 640 | **960 (shipped)** |
|---|---|---|
| Precision | 0.854 | **0.864** |
| Recall | 0.727 | **0.774** |
| mAP50 | 0.783 | **0.833** |
| mAP50-95 | 0.511 | **0.577** |

**What this says:**

- *Precision 0.864* — when it says "person" it is usually right.
- *Recall 0.774* — at the validation default. At the shipped threshold of 0.18 it
  is **0.824**.
- *mAP50 0.833* — strong detection performance for small aerial targets from a
  9.2 M-parameter model.
- *mAP50-95 0.577* — box localization is good, not just detection.

**Is this good?** YOLO12s scores 48.0 mAP50-95 on COCO, and COCO is mostly large,
well-lit, centred objects. You score **57.7 on small aerial humans**, a harder
problem, from a model a third the size of what most teams reach for.

### Resolution vs training — decomposed

A third measurement lets you separate two variables that would otherwise be
confounded. An earlier checkpoint scored mAP50-95 **0.494** at 640:

```
mAP50-95   0.494   →   0.511   →   0.577
           earlier      final       final
           @640         @640        @960
                     └───────┘  └──────────┘
                     training     resolution
                      +0.017        +0.066
```

**Resolution accounts for ~80 % of the gain, further training ~20 %.** One extra
validation run bought that. Without the middle point you could say only "it got
better," not why.

**A correction worth keeping.** Earlier drafts of this handbook reported "epoch 44
of 100" with the weaker figures. Reading the shipped checkpoint directly shows
`epoch: 58` of a planned 100 (zero-indexed — 59 epochs completed) and
`best_fitness 0.50397`. Training went further than the notes recorded. The lesson
is the same one Part 4 teaches about `model.names`: **read the artefact, do not
trust the note about the artefact.**

---

## 7. Inference parameters

The settings that control detection *after* training, all of which appear in your
tools.

### `conf` — confidence threshold

Covered above. **Yours: 0.18.** Boxes below this are discarded.

### `iou` — the NMS threshold

**Non-Maximum Suppression** is a cleanup step. The model often produces several
overlapping boxes for one person. NMS keeps the highest-confidence box and
deletes others that overlap it by more than the `iou` threshold.

Default is 0.7. Lower is more aggressive (risks merging two people standing close
together); higher keeps more duplicates.

### `max_det` — maximum detections per frame

**Ultralytics defaults to 300. Yours is 1000.**

This one is a real catch and worth explaining well. If a frame contains 400
people and `max_det` is 300, the model silently keeps only the 300
highest-confidence detections and discards the rest. No warning. Your survivor
count is quietly wrong, in the worst possible direction — **it drops the
*lowest-confidence* detections, which in a disaster scene are exactly the
partially-buried people you most need to find.**

Dense VisDrone scenes routinely exceed 300 people. Setting it to 1000 costs
nothing and removes a silent failure mode.

*(A note on how this was found: an earlier version of this reasoning claimed the
cap was already binding on your C2A test set. It was measured and it wasn't. The
argument still holds — it's about the dense footage the system is designed for —
but the specific claim was corrected. Part 9 has the full list of things that got
checked and revised.)*

### `imgsz` — input size

The model resizes every frame to a square of this size before looking at it. This
is one of the most important settings you have, and it caused your worst bug.

**The problem:** a 1280-wide clip at `imgsz=640` gets halved. A person who is 24
pixels tall in the source reaches the network as **12 pixels**. That is below what
the model can reliably resolve. Detections flicker in and out — and **no tracker
can hold an identity across boxes that keep vanishing.**

You measured the effect over the demo clip with `tools/test_imgsz.py`:

| imgsz | detections | unique track IDs |
|---|---|---|
| 640 | 5,502 | 350 |
| **960** | **7,081** | **333** |
| 1280 | 7,050 | 345 |

960 finds the most people *and* fragments them into the fewest identities. 1280
costs more inference for slightly worse tracking.

**Inference speed does not enter this choice**, and knowing why is important:
this runs once, offline, to produce `detections.json`. Nothing in the demo detects
in real time. The on-device speed question is separate and is answered by
`DEVICE_FPS` — see Part 4.

`DETECTION_IMGSZ = 960` is in `backend/config.py` and it ships to the dashboard
via `/api/config`, because a confidence threshold means something different at
640 than at 960 and the two numbers have to be read together.

### `persist` and `stream`

- `persist=True` — keep tracker state between calls. Required for tracking video.
  Without it every frame starts a fresh tracker and every ID is new.
- `stream=True` — yield results one frame at a time instead of building a list of
  every frame in memory. On a long clip, the difference between working and an
  out-of-memory crash.

---

## 8. What you would improve, given more time

Have this ready — "what would you do next?" is a guaranteed question.

**1. Finish training.** Epochs 44–100, particularly the decayed-learning-rate
tail. Expect one to three points of mAP.

**2. Higher-resolution training.** You trained at 640 and infer at 960. Training
*at* 960 would align the two and probably help small-object recall. It costs GPU
time and memory.

**3. Tiled inference (SAHI).** Slice a large frame into overlapping tiles, detect
in each, merge. This is the standard technique for small objects in large images
and would likely be the single biggest accuracy gain available. It multiplies
inference cost, so it needs the Pi benchmark first.

**4. More real aerial disaster data.** C2A is composited. Real post-disaster UAV
imagery is the gap, and it is genuinely hard to obtain.

**5. Test-time augmentation.** Run inference on the frame and its horizontal flip,
merge. Typically one to two points of mAP for double the compute.

**6. Hard-negative mining.** Collect the things the model false-positives on —
shadows, bags, rubble patterns — and add them as explicit negative examples.

---

## What to take from this part

- Detection = boxes + confidence. Tracking is a separate stage.
- Precision is "was I right when I spoke"; recall is "did I find everyone".
- **Your headline argument:** conf 0.18 instead of the F1-optimal 0.37 — recall
  0.824 against 0.775, at a cost of 11 points of precision. About **3 extra false
  alarms per additional survivor found**, because a missed survivor cannot be
  recovered.
- mAP50 **0.833** and mAP50-95 **0.577** at 960 px — strong for small aerial
  targets, and both measured on the split the model was trained for.
- `max_det=1000` prevents a silent truncation that would drop exactly the
  detections you most need.
- `imgsz=960` was chosen from a measured sweep and it is why tracking works.

**Next:** Part 3 is tracking — how 7,081 detections became 333 IDs, why 333 IDs
became 23 survivors, and the two wrong diagnoses that came before the right one.

---

**Sources for the YOLOv12 architecture and benchmark figures:**
[YOLO12 — Ultralytics Docs](https://docs.ultralytics.com/models/yolo12) ·
[YOLOv12: Attention-Centric Real-Time Object Detectors (arXiv)](https://arxiv.org/html/2502.12524v1)

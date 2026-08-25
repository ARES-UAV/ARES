# Part 12 — Glossary

Every term used anywhere in ARES or in this handbook. Terms specific to your
project are marked **[ARES]**.

---

## A

**Anchor box** — A pre-defined box shape a detector adjusts rather than predicting
dimensions from scratch. YOLOv8 onward are *anchor-free*.

**Anchor-free** — Predicting box dimensions directly. Fewer hyperparameters.

**AP (Average Precision)** — The area under the precision-recall curve for one
class. A single number summarising performance across all thresholds.

**Area attention** — YOLOv12's mechanism: split the feature map into *l* equal
regions (default 4) so attention gets a large receptive field without quadratic
cost.

**ASGI** — Asynchronous Server Gateway Interface. The protocol between uvicorn and
FastAPI.

**assumed [ARES]** — A provenance tag. A fixed per-clip constant standing in for a
measurement the prototype cannot make: altitude, FOV, flight track, GPS origin.

**Attention** — A mechanism letting a position consider distant positions when
deciding what it is looking at. Classic attention is quadratic in the number of
positions; YOLOv12 uses area attention to avoid that.

**Augmentation** — Randomly modifying training images (flips, rotations, colour
shifts, mosaic) so the model sees more variety than was collected.

**Autograd** — PyTorch's automatic differentiation. Computes gradients for
backpropagation.

---

## B

**Backpropagation** — The algorithm computing how much each weight contributed to
the loss, via the chain rule. What training actually is.

**Band [ARES]** — One of four ordinal priority levels: `low`, `medium`, `high`,
`critical`.

**`BAND_HYSTERESIS` [ARES]** — 0.03. The deadband around each band cut. See
*Hysteresis*.

**Batch** — A group of images processed together before one weight update.

**`bbox`** — Bounding box. In your contract, `[x1, y1, x2, y2]` — top-left and
bottom-right corners in source-resolution pixels.

**`best.pt`** — Ultralytics' auto-saved checkpoint from the epoch with the best
validation score. What you deploy. Distinct from `last.pt`.

**BoT-SORT** — A tracker with camera-motion compensation and optional
re-identification. ~30% slower than ByteTrack, more occlusion-robust.

**ByteTrack** — Your tracker. Associates in two passes: high-confidence detections
first, then leftover tracks against low-confidence detections. Pairs well with a
low confidence threshold.

---

## C

**C2A** — *Combination to Attention*. A dataset of people in disaster scenes, built
by compositing human figures onto disaster imagery.

**Callback ref [ARES]** — A React ref passed as a function rather than an object.
Used in `App.jsx` because the header does not exist on first render, so an effect
with `[]` deps would run once against `null`.

**Checkpoint** — A saved snapshot of model weights mid-training.

**chosen [ARES]** — A provenance tag. An operating decision rather than a guess
about the world: `imgsz`, confidence threshold.

**Class** — A category a detector can predict. ARES has one: `person` (id `0`).

**`CLUSTER_RADIUS_M` [ARES]** — 15 m. How close two survivors must be to count as
clustered.

**`CLUSTER_REFERENCE_FRAME` [ARES]** — Frame 0. The single frame all *relative*
measurements are taken in, so the assumed flight track cancels out.

**`CLUSTER_SATURATION` [ARES]** — 4. The neighbour count at which the cluster term
saturates at 1.0.

**`cluster_score` [ARES]** — The cluster term as it entered the score, or `None`
when the term was dropped as uninformative. Not the same as `cluster_size`.

**`cluster_size` [ARES]** — How many *other* survivors are within
`CLUSTER_RADIUS_M`. **Excludes self** — 22 means a group of 23.

**COCO** — Common Objects in Context. An 80-class, 118k-image dataset. Your
pretrained weights come from it.

**Confidence** — A 0–1 number the model attaches to each detection. Not a
calibrated probability, but a reliable ordering.

**`CONFIDENCE_THRESHOLD` [ARES]** — 0.18. Deliberately low, for recall.

**Confirmed survivor [ARES]** — A track that has appeared in at least
`MIN_TRACK_FRAMES` frames. 23 of your 333 track IDs.

**`confirmed_frame` [ARES]** — The frame a track's `MIN_TRACK_FRAMES`-th detection
landed on. The dashboard filters on this, not `first_frame`.

**Convolution** — An operation sliding a small kernel over an image, computing
weighted sums. The foundation of CNNs.

**CORS** — Cross-Origin Resource Sharing. Browser security allowing a page from
one origin to fetch from another. Required because the frontend is on `:5173` and
the backend on `:8000`.

**`crf`** — Constant Rate Factor. ffmpeg's quality setting, 0 (lossless) to 51.
Yours is 23.

**CVD** — Colour Vision Deficiency. Affects ~8% of men. Why the priority ramp is
ordinal rather than red-green.

---

## D

**Deadband** — A region around a threshold where no state change occurs. See
*Hysteresis*.

**derived [ARES]** — A provenance tag. Arithmetic on assumed values; inherits their
uncertainty.

**Detection** — One box + class + confidence, in one frame.

**`DETECTION_IMGSZ` [ARES]** — 960. The input size your detections were produced
at. Chosen from a measured sweep.

**`detections.json` [ARES]** — Real model output over the demo clip. The file the
whole demo replays. Gitignored.

**`DEVICE_FPS` [ARES]** — `None`. Nobody has run the Pi benchmark. Renders as "not
yet measured".

**DFL loss** — Distribution Focal Loss. Refines box edge precision.

**DOM** — Document Object Model. The browser's tree of objects representing a page.

---

## E

**Epoch** — One complete pass through the training set.

**`EVENT_SAMPLE_INTERVAL_S` [ARES]** — 1.0 s. How often priority is re-assessed for
the event log. A *sampling rate*, distinct from hysteresis.

---

## F

**FastAPI** — Your Python web framework. Type hints drive validation.

**`+faststart`** — An ffmpeg flag moving MP4 metadata to the front of the file so
playback can begin before the whole file downloads.

**FlashAttention** — A memory-efficient attention implementation. Used by YOLOv12.

**Flat-earth approximation [ARES]** — Treating the ground under the clip as a
plane. Contributes ~1 mm of error over 23 m, so not the limiting factor.

**Flicker [ARES]** — A detection appearing and disappearing across frames. Caused
by objects near the model's resolution limit. What broke your tracking.

**FOV** — Field of View. The angular width the camera sees. Yours is 60°
horizontal.

**FPS** — Frames Per Second.

**Frame edge [ARES]** — A short track near the image boundary. A real person
entering or leaving, **not** a false positive. Only 7% of your short tracks.

---

## G

**Gitignore** — Patterns for files git should never track. **Does not untrack
files already tracked.**

**GSD** — Ground Sample Distance. Metres of ground per pixel.
`GSD = 2·H·tan(FOV/2)/width`. Yours is 0.018 m/px.

---

## H

**Haversine** — A formula for great-circle distance on a sphere. Overkill at
ARES's scale; flat-earth is used instead.

**`HAZARDS` [ARES]** — An empty list. Must stay empty until the classifier exists.

**Heading** — A compass bearing: 0 = north, 90 = east, clockwise. **Not** the
mathematical convention — north takes the cosine.

**HMR** — Hot Module Replacement. Vite swapping a changed module without reloading.

**Hysteresis [ARES]** — Requiring a state change to clear its threshold by a
margin. Prevents a jittering score from oscillating across a band cut.

---

## I

**`imgsz`** — The square size a model resizes each frame to before inference.

**ID switch [ARES]** — One person picking up a second track ID after an occlusion.
**Persistence filtering does not fix this.** Your known limitation.

**Idempotent** — `f(f(x)) == f(x)`. `band_for` is, which lets `/api/survivors`
re-score without drift.

**Inference** — Running a trained model to get predictions. As opposed to training.

**IoU** — Intersection over Union. Overlap area ÷ union area. Used both to decide
whether a detection is a true positive and as the NMS threshold.

---

## J

**JSON contract [ARES]** — The agreed detection record format. The seam between
three people's code. **Not to be changed unilaterally.**

**JSX** — React's HTML-like syntax inside JavaScript. Compiles to function calls.

---

## K

**Kalman filter** — Maintains a position-and-velocity estimate, updating as
observations arrive. Used by trackers to predict where a track will be next.

---

## L

**`last.pt`** — The most recent training checkpoint. Use to *resume*; use
`best.pt` to deploy.

**Leaflet** — Your mapping library. **Needs no API key.**

**Learning rate** — How big a step to take when adjusting weights. Decays toward
the end of training, which is why late epochs refine.

**Loss** — A number measuring how wrong the model is. Detection has three
components: box, class, DFL.

---

## M

**mAP** — mean Average Precision, averaged over classes. You have one class, so
mAP = AP.

**mAP50** — AP at IoU threshold 0.5. "Did you find the person, roughly?" **Yours:
0.775.**

**mAP50-95** — AP averaged over IoU 0.50 to 0.95. "Did you find them *and* draw the
box precisely?" Always much lower. **Yours: 0.494.**

**`max_det`** — Maximum detections per frame. **Yours is 1000, not the default
300**, because 300 silently truncates dense scenes and drops the lowest-confidence
detections first.

**measured [ARES]** — A provenance tag. An actual observation of the actual
system. Exactly one row can earn it and it has not yet.

**`METRES_PER_DEGREE_LAT` [ARES]** — 111,320. From the WGS84 equatorial
circumference ÷ 360.

**`MIN_TRACK_FRAMES` [ARES]** — Derived: `int(MIN_TRACK_SECONDS × CLIP_FPS)` = 60.
Floored at 1 by `tracks.min_track_frames()`.

**`MIN_TRACK_SECONDS` [ARES]** — 2.5. Expressed as a **duration** so it means the
same thing at 24 fps and at 1.5 fps.

**Mosaic** — An augmentation stitching four images into one. Good for small-object
detection.

**Multi-object tracking (MOT)** — Assigning persistent identities to detections
across frames.

---

## N

**Nadir** — Pointing straight down. Assumed by your localization.

**NCNN** — Tencent's ARM-optimised inference runtime. Often fastest on a
Raspberry Pi.

**NMS** — Non-Maximum Suppression. Removes overlapping duplicate boxes, keeping
the highest-confidence one.

**`nc`** — Number of classes in a `data.yaml`. Yours is 1. **The field that broke
your Colab resume.**

---

## O

**Occlusion** — One object hiding another. The main cause of ID switches.

**ONNX** — Open Neural Network Exchange. An open format for representing neural
networks, readable by many runtimes.

**Optimizer** — The algorithm deciding how to change weights given the loss. SGD,
AdamW.

**Ordinal ramp [ARES]** — A colour scale where lightness encodes order. One hue,
monotone. Survives a projector, a photocopy and colour-vision deficiency.

**Overfitting** — Memorising training data rather than generalising. Visible when
validation loss rises while training loss keeps falling.

---

## P

**Path halving** — A union-find optimisation flattening the tree during `find`.

**Persistence filtering [ARES]** — Requiring a track to appear in
`MIN_TRACK_FRAMES` frames before counting it as a survivor. Takes 333 → 23.

**`persist=True`** — Ultralytics: keep tracker state between calls. Required for
video tracking.

**PR curve** — Precision plotted against recall as the confidence threshold
sweeps. `PR_curve.png`. **This is what you chose 0.18 from.**

**Precision** — `TP / (TP + FP)`. "Of everything I said was a person, what fraction
was?" **Yours: 0.845.**

**Props** — Data passed from a React parent to a child. Read-only.

**Provenance [ARES]** — The four-way tagging on `MissionParameters`: assumed,
chosen, derived, measured.

**Pydantic** — Python data validation via type annotations.

---

## R

**R-ELAN** — Residual Efficient Layer Aggregation Networks. YOLOv12's feature
aggregation block.

**Recall** — `TP / (TP + FN)`. "Of all the people there, what fraction did I find?"
**Yours: 0.717 at conf 0.5, 0.831 at 0.18.**

**Re-identification (re-ID)** — Matching a person by appearance rather than
position. Would help with occlusions; costs compute.

**Renormalisation [ARES]** — Dividing by the sum of the weights actually used, so a
dropped term redistributes rather than caps everyone below 1.

**REST** — URLs name resources, HTTP methods name actions.

**`ResizeObserver`** — A browser API firing when an element's size changes. Used in
`App.jsx` to measure the header.

---

## S

**SAHI** — Slicing Aided Hyper Inference. Tiles a large frame, detects in each,
merges. The standard technique for small objects, and your biggest available
accuracy gain.

**Single-linkage clustering** — A cluster is a connected component: A near B, B
near C means all three are one group even if A and C are far apart.

**SLAM** — Simultaneous Localization and Mapping. **Described only** in ARES.

**`stream=True`** — Ultralytics: yield results frame by frame rather than
accumulating all in memory.

**StrictMode** — React's development mode that double-invokes effects to surface
bugs. Not active in production.

---

## T

**Tabular numerals** — A font feature giving every digit the same width. **Why the
header doesn't twitch during playback.**

**Tailwind** — Utility-first CSS. Styles composed from classes in the markup.

**`track_id`** — A persistent per-person identity across frames. `-1` means the
tracker declined to assign one.

**Tokens [ARES]** — CSS custom properties in `tokens.css`. **The only place a
colour is written down.**

**Transfer learning** — Starting from weights pretrained on a large dataset and
fine-tuning. You started from COCO.

**True Positive / False Positive / False Negative** — Found a real person / claimed
one where there is none / missed a real one.

---

## U

**Ultralytics** — The Python package implementing YOLOv8/v11/v12. `.train()`,
`.val()`, `.track()`, `.export()`.

**Union-find (disjoint-set)** — The data structure behind your cluster detection.

**Untracked detection [ARES]** — `track_id == -1`. A real detection with no
identity, so it cannot be de-duplicated. Drawn on the video overlay, excluded from
survivors.

**Uvicorn** — The ASGI server that actually listens on port 8000.

---

## V

**Validation set** — Data held out from training, used to measure progress each
epoch. The model never learns from it.

**Vite** — Your frontend dev server and bundler.

**VisDrone** — A large UAV benchmark dataset. Real drone footage, dense scenes,
small objects.

---

## W

**Warm-up runs [ARES]** — Inference calls made and **discarded** before timing,
because the first calls include model loading and cache warming.

**WGS84** — The coordinate system GPS uses. Its equatorial radius (6,378,137 m) is
where 111,320 comes from.

---

## X

**xyxy / xywh / cxcywh** — Box coordinate conventions. Corners / top-left+size /
centre+size. Your contract uses **xyxy**; YOLO uses cxcywh internally.

---

## Y

**YOLO** — "You Only Look Once." A family of one-stage detectors. The name *is* the
architectural claim.

**YOLOv12s** — Your model. Attention-centric, 9.3 M parameters, 48.0 mAP50-95 on
COCO.

---

## Z

**Zoom level [ARES]** — Map tile scale. OSM renders nothing past 19; your config
allows Leaflet to upscale to 22 and caps auto-fit at 20.

---

## The numbers to know by heart

| Number | What it is |
|---|---|
| **7,081** | Raw detections in the clip |
| **333** | Unique track IDs the tracker issued |
| **23** | Confirmed survivors |
| **0.18** | Confidence threshold |
| **0.831 / 0.740** | Recall at 0.18 vs at 0.5 |
| **0.845 / 0.717** | Precision / recall at epoch 44 |
| **0.775 / 0.494** | mAP50 / mAP50-95 |
| **960** | Detection input size |
| **1000** | `max_det` |
| **2.5 s** | Persistence threshold (= 60 frames here, 3 on a Pi) |
| **23.09 m** | Ground footprint at 20 m altitude |
| **0.018 m/px** | Ground sample distance |
| **11.38 m** | Max pairwise separation of all 23 survivors |
| **15 m** | Cluster radius |
| **0.4 / 0.3 / 0.3** | Priority weights |
| **0.25 / 0.50 / 0.75** | Band cuts |
| **0.03** | Band hysteresis |
| **~40 m** | Measured altitude ceiling for reliable detection |

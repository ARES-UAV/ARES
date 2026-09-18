# Benchmarking YOLOv8s on Qualcomm silicon — and what a swap costs

**Goal:** settle whether YOLOv8s is faster than YOLOv12s on the Dragonwing
RB3 Gen 2. It is already more accurate at 960. If it is also faster, it wins on
both axes and becomes the model.

Everything below uses tooling already in the repo. Nothing new to write.

---

## 0. Before you start

```bash
cd ~/College/ARES
source .venv-qai/bin/activate
python -c "import qai_hub; print(qai_hub.__version__)"
qai-hub list-devices | head     # confirms the token is configured
```

**The token lives in `~/.qai_hub/client.ini` and must never be committed or
pasted anywhere.** If the old one was ever exposed, regenerate it on the AI Hub
console first.

Copy the trained weights in:

```bash
cp ~/Downloads/train/weights/best.pt models/yolov8s_c2a_visdrone.pt
python -c "from ultralytics import YOLO; print(YOLO('models/yolov8s_c2a_visdrone.pt').model.names)"
# must print a single person/human class — not the 80 COCO names
```

---

## 1. Export to ONNX at both sizes (~5 min)

```python
from ultralytics import YOLO
m = YOLO('models/yolov8s_c2a_visdrone.pt')
m.export(format='onnx', imgsz=960, simplify=True)   # → yolov8s_c2a_visdrone.onnx
```

Rename per the repo convention, then repeat for 640:

```bash
mv models/yolov8s_c2a_visdrone.onnx models/yolov8s_960.onnx
# re-export with imgsz=640, then
mv models/yolov8s_c2a_visdrone.onnx models/yolov8s_640.onnx
```

**Both sizes matter.** 960 answers the deployment question; 640 answers the
open NPU-scaling question in `ARES_MEASURED_NUMBERS.md`, which has been sitting
unresolved since August.

---

## 2. Fix the ONNX header (~1 min)

Ultralytics' export leaves the graph output duplicated in `value_info` — a spec
violation ONNX Runtime tolerates and Qualcomm's validator rejects. This cost
four wrong hypotheses last time.

```bash
python tools/fix_onnx_io.py models/yolov8s_960.onnx models/yolov8s_640.onnx
```

Zero operators change. It writes a `.orig` backup beside each file.

---

## 3. Benchmark (~20 min per run, mostly waiting)

```bash
python tools/qualcomm_benchmark.py \
    --model models/yolov8s_960.onnx \
    --device "Dragonwing RB3 Gen 2 Vision Kit" --device-os 1.6 --quantize

python tools/qualcomm_benchmark.py \
    --model models/yolov8s_640.onnx \
    --device "Dragonwing RB3 Gen 2 Vision Kit" --device-os 1.6 --quantize
```

**`--quantize` is not optional.** The Hexagon HTP is an integer-only
accelerator; a float32 model is rejected at compile, not at runtime.

The script reads the input size from the graph rather than trusting a flag,
calibrates on 64 frames spread across the demo clip, records the **median** of
~100 samples (not the minimum), writes one JSON per configuration to
`experiments/qualcomm/`, and regenerates `experiments/QUALCOMM_BENCHMARK.md`
from all of them. It cannot overwrite the existing v12s results.

For the second data point, repeat with
`--device "Dragonwing IQ-9075 EVK" --device-os 1.9`.

---

## 4. The decision, written before the numbers arrive

YOLOv8s already wins accuracy at 960: **+263 people found, 2,273 fewer false
alarms, mAP50 0.8453 vs 0.8330.** So the only open axis is latency.

| v8s @960 on RB3 | Verdict |
|---|---|
| **faster than 209.5 ms** | Wins on both axes. **Swap.** |
| **slower than 209.5 ms** | **Keep YOLOv12s.** |

That second row is not a close call. At 4.8 FPS the frame rate is already the
binding constraint on *counting* survivors and on running RGB + thermal
together. A model that is slightly more accurate and slower makes the two
things that are actually broken worse. Accuracy is not the scarce resource
here; frame rate is.

### What the numbers would mean

| latency @960 | FPS | reading |
|---|---:|---|
| < 70 ms | > 14 | Transformative. Fusion becomes free; the counting problem likely dissolves. |
| 70 – 150 ms | 7 – 14 | Real gain. Worth swapping, but re-run the frame-rate study before claiming the tracker conclusion still holds. |
| 150 – 209 ms | 4.8 – 6.7 | Marginal. Swap only if the doc churn is affordable; the honest answer may be "not worth it this month". |
| > 209 ms | < 4.8 | Keep v12s. Architecture question closed. |

---

## 5. If it wins — the real cost of swapping

Be clear-eyed. The detector is upstream of everything, so a swap re-derives the
whole chain. This is roughly **2–3 days** of careful work.

**Regenerate, in this order:**

1. `tools/ingest_video.py` on the demo clip → a new `detections.json`.
   **The survivor count will change.** 23 is a v12s number.
2. `backend/config.py` — model path, `DEVICE_FPS`, `DEVICE_NAME`, and a
   **newly chosen `conf`** off the v8s PR curve (its F1-optimal is 0.353, not
   v12s's 0.371 — do not inherit 0.18 without re-deriving it).
3. `simulation/config.py` — `P_DETECT` is currently **0.824**, which is v12s's
   recall at conf 0.18. Replace with v8s's, then **re-run 100 seeds**. The
   headline 20/20-vs-11/20 and 3.21× figures may move.

**Then update every file that quotes a v12s-derived number:**
`README.md` · `REPORT.md` · `RUNBOOK.md` · `docs/index.html` ·
`experiments/ARES_MEASURED_NUMBERS.md` · the handbook chapters ·
**the SIH deck** (model name, params, recall, the architecture diagram) ·
and the demo video if it shows detections.

**The item most likely to overrun:** `experiments/FRAME_RATE_STUDY.md`. Its
entire premise is 4.8 FPS. If v8s changes the frame rate materially, **the
BoT-SORT-over-ByteTrack conclusion may flip** — ByteTrack collapsed *because of*
the low frame rate, and it is the cheaper tracker. That is a genuine re-run, not
a find-and-replace.

### The staging that protects the deadline

| | |
|---|---|
| **Day 1** | Steps 1–3 above. Half a day. Decision made on a measured number. |
| **Days 2–3** | Regenerate `detections.json`, config, re-run 100 seeds, update docs. |
| **Day 4** | Re-run the frame-rate study **only if** FPS changed materially. |
| **Day 5** | Re-cut the deck and the video. |

That leaves the buffer intact against the 30 September deadline — but only if
the benchmark happens now rather than in a week.

### One rule to hold

**Do not update the deck or any document until `detections.json` has been
regenerated and the counts reconcile.** The failure mode this project has hit
twice is a number written down before its source was re-checked. A half-swapped
repo, where the docs say YOLOv8s and the dashboard replays YOLOv12s output, is
worse than either model shipped cleanly.

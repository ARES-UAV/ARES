# G1 — AI & Model

**Owner:** Dewang + 1 · **Window:** 6 – 27 September · **Deadline:** 30 September (confirmed)

You own everything that turns pixels into detections. Nobody else touches the
models.

---

## Context you need before starting

**What already works.** ARES has two trained detectors:

| | RGB | Thermal |
|---|---|---|
| Model | YOLOv12s | YOLOv8s |
| Data | C2A + VisDrone, 59 epochs | HIT-UAV + AIResQ, 104 epochs |
| Precision | 0.864 | 0.921 |
| Recall | **0.774** (0.824 at conf 0.18) | **0.883** |
| mAP50 | 0.833 | 0.927 |
| Weights | `models/yolov12s.pt` | **not in the repo — see task 0** |

**The contract.** Everything you produce leaves as a JSON array of:

```json
{"frame_id": 0, "bbox": [x1,y1,x2,y2], "confidence": 0.87, "track_id": 2, "class": 0}
```

Pixel coordinates, original resolution. `track_id: -1` means untracked.
**This format is shared with G2 and G3. Do not change it — flag it instead.**
Everything downstream (localization, priority, the dashboard, the flight loop)
reads this and nothing else.

**Ship settings, from `backend/config.py` — never retype a number:**
`imgsz=960`, `conf=0.18`, `max_det=1000`, tracker BoT-SORT.

`conf=0.18` is deliberately low. It was picked off the validation PR curve, not
defaulted: it costs 11 points of precision and buys 5 points of recall — about
three extra false alarms per additional person found. A missed survivor is not
recoverable; a false box costs an operator one second.

`max_det=1000` because scenes routinely hold more than the default 300 people.

---

## Task 0 — publish the thermal weights (do this first, 20 minutes)

The thermal metrics are in `experiments/THERMAL_MODEL.md`. **The weights are
nowhere a teammate can reach.** Weights are gitignored on purpose — they go to a
GitHub Release.

```bash
gh release create thermal-v1 /path/to/thermal_best.pt \
  --title "Thermal person detector v1" \
  --notes "YOLOv8s, epoch 101, HIT-UAV + AIResQ, P 0.921 / R 0.883 / mAP50 0.927"
```

**Done when:** someone else can download it from a URL.

---

## Task 1 — thermal provenance (half a day)

`THERMAL_MODEL.md` §6 lists four things missing before those numbers can be
quoted. The RGB numbers carry their provenance — *"2,591 images · 86,092
instances"*. The thermal ones do not.

1. **Validation split size** — how many images and person instances is 0.883
   measured over?
2. **How the split was made** — random over the combined pool, or held out per
   dataset? This matters: HIT-UAV is 2,898 images and AIResQ is 9,788, so a
   random split mostly measures AIResQ.
3. **Per-dataset recall** — HIT-UAV alone, AIResQ alone. If they differ sharply
   the combined number hides it, and *"does it work on real drone footage?"* is
   answered by the HIT-UAV row specifically. (AIResQ was shot from cable cars
   and towers, not drones — that is disclosed, not hidden.)
4. **Pick an operating threshold** off the thermal PR curve the same way 0.18
   was picked for RGB, and write down what it costs.

```bash
yolo detect val model=thermal_best.pt data=<your.yaml> imgsz=960 split=val
# then per-dataset, by pointing data= at a yaml holding only one source
```

**Done when:** `THERMAL_MODEL.md` §6 is deleted because all four are answered.

---

## Task 2 — wire the thermal detector into the pipeline (half a day)

Write `tools/fuse_detections.py`. Run both models over one clip, fuse the
outputs, write **one** `detections.json` in the contract format above.

The fusion rule is already written and tested in `tools/fuse_eval.py`:

```
C_fused = w_r · C_rgb + w_t · C_thermal        w_r + w_t = 1
```

Boxes that both sensors saw are matched by IoU and their confidences combine. A
box only one sensor saw gets the other's vote as **zero**, so it is penalised.
That is the whole mechanism: agreement is rewarded, single-sensor guessing is
not. A hot car reads as a person to thermal alone; RGB not confirming it drops
it below threshold.

**This is late fusion (decision level), not early fusion (a 4-channel network).**
Three reasons, and a judge will ask:

- it uses the two models that already exist — early fusion needs a new
  architecture and a full training run
- it degrades gracefully; lose the thermal camera mid-flight and RGB keeps
  working, where a 4-channel net handed a dead channel does something undefined
- *"both sensors saw something here"* is a sentence a judge can check

**Fusion sits upstream of the contract.** The fused output is still
`detections.json` in the existing format, so G2's backend, the dashboard and
G3's loop all keep working untouched.

**Done when:** the script runs end to end and produces a valid contract file.

---

## Task 3 — measure fusion on paired data (1.5–2 days, mostly unattended GPU)

**Start the download on day one; the fine-tunes run while you do Task 4.**

Neither of your thermal datasets can do this: HIT-UAV and AIResQ are thermal
only, C2A and VisDrone are RGB only. Fusion needs the *same scene* in both,
pixel-registered. That needs a paired set.

**LLVIP** — 15,488 registered visible/infrared pairs, pedestrians labelled,
night scenes. Download needs a short form.
→ https://bupt-ai-cz.github.io/LLVIP/

```bash
# two short fine-tunes, ~4-6 h GPU total, unattended
yolo detect train model=models/yolov12s.pt data=llvip_visible.yaml \
     epochs=30 imgsz=960 name=rgb_llvip
yolo detect train model=<thermal best.pt> data=llvip_infrared.yaml \
     epochs=30 imgsz=960 name=ir_llvip

# predict both on the same test images, then
python tools/fuse_eval.py --rgb rgb_preds.json --thermal ir_preds.json \
                          --gt llvip_test_gt.json --w-rgb 0.5
# sweep --w-rgb 0.3 0.4 0.5 0.6 0.7 and report which you picked and why
```

**The number that matters is false positives at equal recall — not raw recall.**
LLVIP is all night scenes, so thermal will beat RGB by a wide margin and fusion
will land near thermal. That is a *"thermal works in the dark"* result, which
nobody doubts, and it is not a fusion result. `fuse_eval.py` prints the
equal-recall comparison as its second table. Quote that one.

**Say this before a judge does:** LLVIP is street-level surveillance, not
aerial. No paired RGB+thermal *aerial* person-detection dataset exists publicly.
So this demonstrates the mechanism on the standard benchmark; the aerial version
needs data that does not exist yet. That is a finding about the field, not a gap
in your work.

**Done when:** a table of RGB-only / thermal-only / fused with false positives
held at equal recall.

---

## Task 4 — hazard classifier (2 days)

Three classes only: **fire/smoke, flood, collapsed structure.** Not seven. The
SIH plan document says this itself — do not claim seven strong classes when
three have evidence.

Train on **AIDER** (UAV-native, ~8,540 images), same pipeline as the survivor
model.

Then the part that matters downstream: **populate `config.HAZARDS`.** Until it
is populated, the hazard term in the priority score drops out entirely and G2's
planner has no risk input. Two things unblock the moment this lands.

**Publish per-class metrics.** A class without its own precision/recall row gets
dropped from the claim.

**Done when:** per-class metrics exist in `experiments/`, and `config.HAZARDS`
has real entries.

> **Never hand-author a hazard to make the map look livelier.** It is the same
> failure as fabricating detections and it destroys the honest-scoping story,
> which is this project's strongest asset with judges. An empty hazard list is
> a correct state.

---

## Task 5 — INT8 accuracy (half a day)

Right now **every latency figure is INT8 and every accuracy figure is FP32.**
They are two different models until someone measures the quantised one. It is
the only gap between the project's two headline tables, and it is the kind of
thing a technically strong screener notices.

Validate the INT8 export on the same combined val split and report the delta.

**Done when:** the accuracy table has an INT8 column, however bad it looks.
A measured drop is a result. An unmeasured one is a hole.

---

## Task 6 — the perception node for the closed loop (2 days, from ~17 Sept)

G3 is building a simulated flight where the aircraft actually flies and a
camera actually renders. You provide the perception.

Wrap detection + tracking as a function G3 can call per frame:

```python
def perceive(frame_bgr, frame_id: int) -> list[dict]:
    """One rendered frame in, contract records out. Same weights,
    same conf 0.18, same imgsz 960, same tracker as the offline path."""
```

**Do not fork the settings.** If the loop runs different parameters from the
shipped pipeline, its results cannot be compared to anything already measured.

**The one risk to check early — the domain gap.** Your detector was trained on
real aerial photographs. If G3's renderer produces anything that does not look
like real aerial imagery, recall will collapse and it will look like a model
failure when it is a rendering failure. Ask G3 for ten sample frames the day
they have them and run the detector over them **before** anyone builds on top.
If recall is far from 0.774, say so immediately — that is a design bug in the
renderer, not in your model, and it is cheap to fix early and expensive to fix
late.

---

## What not to do

- Do not change the JSON contract. Flag it; it affects all three groups.
- Do not re-tune `conf`, `imgsz` or `max_det` without a measurement that
  justifies it. The current values were each chosen off evidence.
- Do not fabricate a detection or a hazard, ever, for any reason.
- Do not quote the thermal numbers publicly until Task 1 closes.
- Do not present thermal as "beating" RGB. Different datasets, splits and
  architectures. The honest reading is the *shape*: thermal detects more easily
  (higher recall and mAP50) and localises less precisely (lower mAP50-95),
  because a warm body is a high-contrast blob with soft edges. That pattern is
  what thermal physics should produce, and saying so is stronger than a
  comparison you cannot support.

## Where the numbers live

`experiments/ARES_MEASURED_NUMBERS.md` is the single source of truth. Every
figure you produce goes there with what it was measured over. Nothing goes in
the deck that is not in that file first.

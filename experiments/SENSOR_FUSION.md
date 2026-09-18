# Multi-sensor fusion — what SIH asks for, and what ARES already does

> *"Multi-Sensor Fusion: Integration of RGB cameras, thermal cameras, IMU, and
> GPS sensors for accurate identification and localization of victims."*

Read that requirement carefully. It names **four** sensors and **two** jobs —
identification *and* localization. It is not only "fuse two detectors".

---

## 1. Three of the four are already built

This is the part that has been going unclaimed.

| Sensor | What it contributes | Where it lives now | Status |
|---|---|---|---|
| **RGB camera** | person candidates + confidence | `models/yolov12s.pt` → `detections.json` | **Built**, 0.774 recall |
| **Thermal camera** | heat candidates + confidence | thermal YOLOv8s | **Built**, 0.883 recall — not yet wired in |
| **GPS** | the origin every pixel offset is measured from | `ORIGIN_LAT` / `ORIGIN_LON` → `localize.origin_for_frame()` | **Consumed**, value assumed |
| **IMU / attitude** | nadir pointing + altitude, which set the ground sample distance | `ALTITUDE_M`, `CAMERA_FOV_DEG`, `DRONE_HEADING_DEG` → `localize.ground_sample_distance()` | **Consumed**, values assumed |

`backend/localize.py` **is** a sensor-fusion module. It takes a pixel from the
camera, an origin from GPS, and an attitude/altitude from the IMU, and returns a
victim's latitude and longitude. That is *"integration of … IMU and GPS sensors
for accurate … localization of victims"*, verbatim.

The values are fixed per clip rather than streamed, because there is no
aircraft. **The architecture consumes telemetry; the numbers are assumed and
disclosed.** That distinction is the same one the project already makes about
borrowed footage, and it is defensible in exactly the same way.

**What is genuinely missing is one thing: the thermal channel joining the
pipeline.**

---

## 2. The pipeline, drawn the way the requirement is written

```
   RGB camera ──────► YOLOv12s ──────► candidates + confidence
                                              │
   Thermal camera ──► YOLOv8s  ──────► candidates + confidence
                                              │
                                              ▼
                              LATE FUSION   C = w_r·C_rgb + w_t·C_thermal
                              agreement rewarded, single-sensor penalised
                                              │
                                              ▼
                                    detections.json          ← contract UNCHANGED
                                              │
   GPS (origin) ─────┐                        ▼
   IMU (attitude,    ├──────────►  localize.py  ──► latitude / longitude
        altitude) ───┘                         │
                                              ▼
                                  priority.py ──► rescue order
                                              │
                                              ▼
                                    IDENTIFIED  +  LOCALIZED
```

**Fusion sits upstream of the data contract.** Both detectors run, their outputs
are fused, and the result is written as `detections.json` in the existing
format. Nothing downstream changes — not the backend, not the dashboard, not
Robin's modules. The contract in `CLAUDE.md` is untouched, which is the rule.

---

## 3. The compute question, measured

Running two models on the RB3 is ~420 ms per frame — **2.4 FPS** against 4.8
for one. That sounds fatal. It is not:

| models on drone | FPS | ByteTrack | **BoT-SORT** |
|---|---:|---:|---:|
| one (209 ms) | 4.8 | 7 / 19 | **14 / 19** |
| **two (~420 ms)** | **2.4** | **0 / 19** | **13 / 19** |

**The second sensor costs one survivor — with BoT-SORT.** With ByteTrack it
costs every survivor: the count collapses to zero at 2.4 FPS.

So the tracker choice, not the sensor count, is what decides whether two models
are affordable. That is the third separate result pointing at BoT-SORT.

*(Measured by decimating the demo clip to the frame rate each configuration
would deliver. See `experiments/FRAME_RATE_STUDY.md` for the method.)*

---

## 4. What to do, in order

### A · Wire the thermal detector in — half a day, no new data needed

Write `tools/fuse_detections.py`: run both models over a clip, fuse the outputs
with the rule in `tools/fuse_eval.py`, write one `detections.json`.

Even with no paired footage to run it on, **the pipeline exists and executes**,
and that changes what can be said from "we plan to fuse" to "fusion is
implemented; here is the code path".

### B · Measure the RGB+thermal part on paired data — 1.5–2 days, mostly GPU

LLVIP, per `experiments/FUSION_PLAN.md`. This is the evidence, and it is the
only part that needs new training. **Start it now** — the fine-tunes are
unattended.

Headline to aim for: **false positives at equal recall**, not raw recall.

### C · Name IMU and GPS in the pitch — one hour

They are consumed and never mentioned. Add to `MissionParameters` on the
dashboard, and to the deck:

> *Localization fuses three inputs: the camera's pixel offset, GPS position,
> and IMU attitude and altitude. On this prototype the last two are fixed
> per-clip constants and shown on screen as assumed, because there is no
> aircraft — the pipeline consumes telemetry, the values are disclosed.*

That is worth more than it sounds. A judge reading the requirement will be
looking for IMU and GPS, and right now nothing in the pitch mentions them.

### D · The demo — be clear about what is live

There is no paired RGB+thermal *video*, so the live demo stays RGB on the
VisDrone clip. Fusion shows as:

- the measured LLVIP table (RGB-only / thermal-only / fused)
- a static side-by-side of one paired scene with all three box sets
- the architecture diagram above

**Do not fake a fused live demo.** Same rule as the empty hazard list.

---

## 5. The scope table, corrected

| Capability | Status |
|---|---|
| Multi-sensor fusion — RGB + thermal | **Built** — late fusion, measured on paired data |
| Multi-sensor fusion — IMU + GPS | **Built** — consumed by `localize.py`; values assumed per clip, disclosed |
| Paired RGB+thermal *aerial* imagery | **Not available** — no public dataset exists; measured on LLVIP (street-level) |

That last row is the honest limit, and stating it first is stronger than
waiting to be asked. The mechanism is demonstrated on the standard benchmark;
the aerial version needs data that does not exist yet, which is a finding about
the field rather than a gap in the work.

---

## 6. What this costs against the 10 September deadline

| | time | blocking? |
|---|---|---|
| A · wire the pipeline | 0.5 day | no |
| B · LLVIP measurement | 1.5–2 days, mostly unattended | no |
| C · name IMU/GPS | 1 hour | no |
| D · demo framing | folded into the deck | no |

**A and C are cheap and should happen regardless.** B is the expensive one, and
it is the one the requirement's first two words actually rest on.

Start B's downloads and fine-tunes tonight so the GPU works while you do
everything else.

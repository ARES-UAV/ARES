# Part 1 — What ARES Is

## The problem

An earthquake flattens part of a city. A flood cuts off a district. Somewhere in
the rubble or the water there are people alive, and the single most valuable
thing a rescue coordinator can have in the first six hours is an answer to two
questions:

1. **How many people are there, and where?**
2. **Who do we go to first?**

Traditionally that answer comes from someone flying a drone and watching the
video feed on a tablet. A human watching a screen. That works, and it has three
failure modes:

- **Attention.** A person watching aerial video for forty minutes misses things.
  Survivors in rubble are small, partly buried, and do not wave.
- **Counting.** The same person walks in and out of frame six times. Was that six
  people or one? A human watching live has no reliable way to know.
- **Bandwidth.** Streaming HD video back to a command post needs a network. In a
  disaster zone there isn't one.

ARES addresses all three by moving the analysis **onto the drone**. A model runs
on the aircraft, detects people, keeps track of who is who, works out where they
are on a map, ranks them, and sends back a few kilobytes of structured data
instead of a video stream.

That last point is worth sitting with, because it is the actual engineering
argument and it is the one judges respond to. **Offline resilience is not a
feature you built — it is a consequence of the architecture.** If the analysis
happens on the aircraft, then losing the network costs you the video feed and
nothing else. The survivor count, the map positions and the priority ranking are
already computed.

---

## The four stages

Everything in ARES is one of four things. Each stage exists because the previous
stage produces something that is not yet useful.

```
   VIDEO FRAMES
        │
        ▼
┌─────────────────┐
│  1. DETECTION   │   "there is a person at these pixels, I'm 0.67 sure"
└─────────────────┘
        │  boxes, one per person per frame — but no identity
        ▼
┌─────────────────┐
│  2. TRACKING    │   "that box in frame 12 is the same person as frame 11"
└─────────────────┘
        │  boxes with persistent IDs — but positions are still in pixels
        ▼
┌─────────────────┐
│ 3. LOCALIZATION │   "that pixel is 26.4063°N, 92.2339°E on the ground"
└─────────────────┘
        │  people on a map — but no ordering
        ▼
┌─────────────────┐
│ 4. PRIORITY     │   "go to this one first, and here is why"
└─────────────────┘
        │
        ▼
    DASHBOARD
```

### Stage 1 — Detection

A neural network looks at one frame and outputs boxes: *there is a person here,
and here, and here.* Each box comes with a confidence between 0 and 1.

This is what your YOLOv12s model does. Part 2 covers it completely.

**What detection alone cannot do:** it has no memory. Frame 11 and frame 12 are
two unrelated questions to it. If you count the boxes across a 300-frame clip you
get 7,081 detections, and there are twenty-three people.

### Stage 2 — Tracking

A tracker looks at the boxes in frame 12, compares them to the boxes in frame 11,
and decides which is which. It assigns each person a `track_id` that persists.

Now you can answer *how many people* — count the distinct IDs rather than the
boxes.

**What tracking alone cannot do:** it gives you identity but not location. A
`track_id` and a pixel coordinate tell a rescue team nothing they can act on. And
critically, the raw ID count is still wrong — your tracker emits **333 IDs for
about 23 people**. Part 3 is entirely about why, and what to do about it.

### Stage 3 — Localization

Convert pixel coordinates to latitude and longitude. If you know the drone's
altitude, its camera's field of view, and its GPS position, then a pixel offset
from the centre of the frame is a *ground* offset from the drone's position, and
that is a coordinate.

This is `backend/localize.py`, and the maths is derived in full in Part 6.

**What localization alone cannot do:** it puts twenty-three pins on a map. A
coordinator with limited teams still has to decide where to send them.

### Stage 4 — Priority

Rank the survivors. Yours uses a weighted average of three things: how confident
the detector is, how many other survivors are nearby, and how close the nearest
hazard is.

That's `backend/priority.py`. Part 6 derives it and Part 9 explains why it is a
transparent formula rather than a learned model.

---

## The seam: the data contract

The four stages are owned by different people. Stages 1 and 2 are yours; 3 and 4
are Robin's; the dashboard is yours again. If everyone's code had to import
everyone else's code, nobody could work independently — Robin would need
Ultralytics and PyTorch installed just to test a distance calculation.

So there is a **contract**. One JSON format that stages 1–2 write and stages 3–4
read:

```json
{
  "frame_id": 0,
  "bbox": [x1, y1, x2, y2],
  "confidence": 0.87,
  "track_id": 2,
  "class": 0
}
```

| Field | Meaning |
|---|---|
| `frame_id` | Zero-indexed frame number in the source video |
| `bbox` | Pixel coordinates: top-left corner, bottom-right corner |
| `confidence` | How sure the detector is, 0.0 to 1.0 |
| `track_id` | Persistent per-person ID. `-1` means the tracker declined to assign one |
| `class` | Always `0` (person). Hazard classes arrive in Phase 2 |

**This is the single most important design decision in the project**, and it is
worth being able to explain why:

- **It decouples the team.** Robin reads a JSON file. He does not need your model,
  your weights, or a 2 GB PyTorch install to develop against real data.
- **It decouples the demo from inference.** Because the contract is a file, the
  demo can *replay* a stored file rather than running the model live. That removes
  every live-inference failure mode from the stage.
- **It is a boundary you can test.** A file either matches the schema or it does
  not. `backend/schemas.py` validates it on the way in.

The rule around it: **do not change it unilaterally.** A change touches three
people's code. Flag it instead.

Note what is *not* in the contract: latitude, longitude, priority score. Those
are **derived** server-side. The contract carries what the model *saw*; the
backend adds what it *concluded*. Keeping those apart is what lets you say
honestly that the detections are real model output.

---

## The one number that matters

Ask yourself what this entire system is for. It is for telling a rescue
coordinator how many people are down there.

That means the number that matters is **the count of distinct people**, and
almost everything in the codebase exists to protect it:

| Number | What it is | Value on your clip |
|---|---|---|
| Raw detections | Every box the model drew, all frames | 7,081 |
| Unique track IDs | Every identity the tracker issued | 333 |
| **Confirmed survivors** | Tracks that persisted ≥ 2.5 seconds | **23** |

Those are three different questions with three different answers, and the
dashboard shows all three side by side, labelled. That is not padding — a judge
who sees only "23" has to take it on faith, and a judge who sees 7,081 → 333 → 23
can see the filtering happen.

The gap between 333 and 23 is the price of running the detector at a deliberately
low confidence threshold. Part 3 explains why that trade is the right one for
search and rescue.

---

## The two architectures

There is a real system and a demo system, and confusing them is a good way to
give a bad answer on stage.

### What ARES is designed to be

```
Drone in flight — the loop closes here, with the radio switched off
  ┌─→ camera → detection (YOLO, INT8, on the companion computer)
  │      → ByteTrack assigns IDs
  │      → pixel → GPS using onboard telemetry
  │      → priority scoring
  │      → belief update over the search grid
  │      → planner picks the next target
  │      → flight controller flies to it
  └──────┘

Radio link (optional) → a few KB of JSON → command dashboard
```

**Everything that decides anything runs on the aircraft.** The ground station
is where people look, not where choices are made:

> *"The link carries information out, not commands in. Losing it costs the
> operator live awareness. It does not stop the search."*

The reason this is affordable is bandwidth, not latency. Streaming 1280×720
video needs ~3,000 kbps; sending confirmed survivor records once a second needs
~22 kbps — **about 136× less.** The whole demo mission, all 23 survivors, is
**2.7 KB**. On-device inference turns a video-bandwidth problem into a
text-bandwidth problem.

The planner is the newest stage and the one to be careful about: it is
**designed** to run onboard and has been **measured** to fit there (below), but
it has only ever been flown in simulation. See `simulation/` and
`docs/PRIORITY_PRIOR_AND_OFFLINE.md` § 3–4.

### Does one drone have the compute for all that?

Measured on the project's own code rather than estimated, with an 8× pessimistic
allowance for ARM:

| Stage | Time | Runs |
|---|---:|---|
| **Detection @960 INT8** | **209.5 ms** | every frame *(measured on RB3 Gen 2)* |
| Localization, 23 survivors | 0.25 ms | every frame |
| Priority scoring, O(n²) | 1.57 ms | every frame |
| **Planner — 400 cells + argmax** | **0.28 ms** | **once per 20 s** |

Everything downstream of detection costs **0.87 % of the frame budget**, and the
planner's duty cycle is **0.0014 %**. Detection is the whole cost; the
intelligence is free. What is genuinely hard is running *two* detectors for
RGB + thermal fusion (measured: 2.4 FPS), and sustained thermal and power draw,
which is **not measured**.

### What the demo actually does

```
detections.json  ──►  FastAPI backend  ──►  React dashboard
(pre-computed)        localize + score       map + tables + video
```

The demo **replays a pre-computed file against a playback clock.** It does not
run inference. This is deliberate, disclosed, and a judge should hear it from you
before they work it out:

> "The detections you're watching are real output from our trained model, run
> over this clip ahead of time. We replay them against a playback clock rather
> than running inference live, because live inference on stage adds a failure
> mode that proves nothing — the model already ran, and this is what it produced."

That is a stronger answer than a live demo that might crash. It is also *true*,
which the alternative framing would not be.

---

## What is real and what is described

This table is in `CONVENTIONS.md` and it belongs in the pitch. Judges reward honest
scoping; they punish claims that fall over under one question.

| Capability | Status |
|---|---|
| On-device AI inference | **Built** |
| Emergency alerting / priority scoring | **Built** |
| Command centre dashboard | **Built** |
| Geo-tagged mapping | **Built** |
| Offline resilience | **Built** — a consequence of on-device inference |
| Multi-sensor fusion (RGB + thermal) | *Partial* — public thermal datasets, not hardware |
| Hazard classification | *Partial* — 3 of 7 classes, Phase 2 |
| Adaptive search planning | *Simulated* — 100-seed study vs a lawnmower baseline. **Never flown** |
| Autonomous navigation, GPS-denied SLAM | **Described only** — architecture write-up |

The rule: **do not build, mock, or imply the "described only" row.** An
architecture diagram for SLAM is honest. A dashboard panel showing a SLAM map
that isn't real is not.

---

## The demo footage policy

There is no physical drone. So where does the video come from?

**Public UAV datasets** — VisDrone-VID sequences, UAV123, free stock aerial
footage. And `detections.json` is produced by **running your actual trained model
over that footage**.

This distinction is everything:

- ✅ **Borrowed clip, real detections.** Normal for a prototype. The flight is
  borrowed; the perception is yours. Say so and nobody blinks.
- ❌ **Borrowed clip, invented boxes.** One question destroys it, and it destroys
  your credibility on everything else you said.

`backend/data/fixture_detections.json` existed only so the frontend could be
built before real footage was processed. It is development scaffolding. It must
never appear in a demo, a screenshot, or the recorded video.

---

## Map of the repository

```
ARES/
├── CONVENTIONS.md                  ← project context; the rules this repo runs on
├── README.md                  ← public-facing summary
├── requirements.txt           ← backend deps: fastapi, uvicorn, pydantic. That's all.
│
├── backend/                   ← the API (Part 5)
│   ├── config.py              every tunable constant, heavily justified
│   ├── schemas.py             Pydantic models — the API's type system
│   ├── tracks.py              persistence filtering: which IDs are survivors
│   ├── localize.py            pixel → GPS
│   ├── priority.py            the scoring formula
│   ├── events.py              the mission timeline
│   ├── main.py                the routes
│   └── data/
│       ├── detections.json    real model output (gitignored)
│       ├── demo_clip.mp4      the footage (gitignored)
│       └── tiles/             cached map tiles (gitignored)
│
├── frontend/                  ← the dashboard (Part 7)
│   ├── src/
│   │   ├── App.jsx            the playback clock and shared state
│   │   ├── config.js          frontend constants + the offline fallback
│   │   ├── api.js             all backend fetching
│   │   ├── tokens.css         the validated colour palette
│   │   ├── detectionIndex.js  derived counts, computed once
│   │   ├── missionLog.js      the event log's entries
│   │   ├── clock.js           frame → timecode
│   │   ├── theme.js           token values for canvas and Leaflet
│   │   └── *Panel.jsx         the six panels
│   └── public/
│       ├── demo_clip.mp4      the video the browser plays
│       └── static/            the backend-off fallback bundle
│
├── ai/requirements.txt        ← ML deps: ultralytics, torch, onnx (~2 GB)
│
├── tools/                     ← offline scripts (Part 8)
│   ├── build_demo_clip.py     run the model over footage → detections.json
│   ├── test_imgsz.py          the input-size sweep
│   ├── compare_trackers.py    ByteTrack vs BoT-SORT
│   ├── analyse_tracks.py      how many track IDs are real people
│   ├── survey_visdrone.py     pick a sequence
│   ├── fetch_tiles.py         download map tiles for offline use
│   ├── benchmark.py           FPS measurement
│   └── make_fixture.py        the development scaffolding generator
│
└── experiments/
    └── MODEL_SELECTION.md     the model comparison, with numbers
```

Notice the shape: **two dependency files.** The backend needs three packages.
The ML work needs about two gigabytes. They are deliberately separate, because
the dashboard must be trivially easy to set up on a teammate's laptop and on
whatever machine runs the demo.

---

## What to take from this part

1. Four stages, each solving a problem the previous one leaves behind.
2. The JSON contract is the seam that lets three people work independently.
3. Three counts — detections, track IDs, confirmed survivors — and knowing which
   is which is the difference between understanding this project and reciting it.
4. The demo replays a file. That is a strength, stated confidently.
5. Real detections over borrowed footage. Never invented boxes.

**Next:** Part 2 takes the detection stage apart completely — what YOLO is, what
every training number means, and what your model's numbers actually say.

# ARES — Runbook

Fresh laptop to live dashboard, and any video to live dashboard. Nothing
assumed, every failure named.

1. [Where each stage runs](#1-where-each-stage-runs)
2. [Fresh laptop → live dashboard](#2-fresh-laptop--live-dashboard)
3. [A judge hands you a video](#3-a-judge-hands-you-a-video)
4. [What breaks, and what to do](#4-what-breaks-and-what-to-do)
5. [The offline path](#5-the-offline-path)

---

## 1. Where each stage runs

The single most useful thing to know: **detection and tracking do not run at
demo time.** They run once, offline, and write a file. The dashboard replays
that file against a clock. This is `CLAUDE.md`'s demo-day constraint 1 and it
removes every live-inference failure mode from the stage.

| Stage | Runs | Where exactly |
|---|---|---|
| **Detection** | Offline, once | `tools/ingest_video.py` → `backend/data/detections.json` |
| **Tracking** | Offline, once | Same script. Track IDs are baked into that file. |
| **Persistence filter** | **Backend** | `backend/tracks.py`, applied inside `/api/survivors` |
| **Localization** (pixel→GPS) | **Backend** | `backend/localize.py`, inside `/api/survivors` |
| **Priority scoring** | **Backend** | `backend/priority.py`, inside `/api/survivors` |
| **Mission log** | **Both** | see below |
| **Playback clock** | **Frontend** | `App.jsx` · `currentFrame`, read off the `<video>` element |
| **Per-frame overlay + counts** | **Frontend** | `detectionIndex.js` |
| **Map** | **Frontend** | Leaflet; tiles served by the backend from `/tiles/...` |
| **Adaptive search** | **Neither** | `simulation/` — a standalone study, **not wired to the dashboard** |

### The mission log is deliberately split

- **Backend** (`/api/events`) produces only the two kinds that need
  server-side maths: **cluster formation** (needs `localize`) and **priority
  band changes** (needs `priority`, and needs the whole history because bands
  are hysteretic).
- **Frontend** (`missionLog.js`) derives the rest — replay start, survivor
  confirmations, the closing summary — **from the survivor roster it already
  holds.**

That is not an oversight. If the frontend counted confirmations itself, the
log's count and the header's count would be two tallies that must agree. This
way they are one list. Same reason `detectionIndex.js` is forbidden from
counting confirmed survivors.

### The four endpoints

| Endpoint | Returns |
|---|---|
| `/api/health` | liveness, for the connection badge |
| `/api/config` | every tunable constant, as one object |
| `/api/detections` | every raw record, unfiltered |
| `/api/events` | cluster + band events |
| `/api/survivors` | confirmed roster, localized, scored, **sorted by priority** |
| `/tiles/{z}/{x}/{y}.png` | one cached OSM tile |

The frontend fetches each **once on mount**. It does not poll.

### Adaptive search is not in the product

`simulation/` is a research study with its own world, planners and metrics. It
shares `backend/config.py`'s constants and nothing else. No dashboard panel
reads it. When the deck says "adaptive search", it is describing that study —
which is why `CLAUDE.md`'s scope table marks it *simulation only, not flown*.

---

## 2. Fresh laptop → live dashboard

### What a clone actually contains

`.gitignore` excludes all model weights (`models/`) and all video except one
deliberate exception. So:

| | in a fresh clone? |
|---|---|
| `backend/data/detections.json` | **yes** — explicitly un-ignored |
| `frontend/public/demo_clip.mp4` | **yes** — explicitly un-ignored |
| `backend/data/tiles/**` (376 tiles) | **yes** — explicitly un-ignored |
| `models/*.pt` — the weights | **no** |
| `backend/data/demo_clip.mp4` | **no**, and it is not needed — the browser plays the `frontend/public/` copy |

**The dashboard runs on a fresh clone with no downloads.** You only need the
weights to ingest a *new* video.

### Prerequisites

- **Python 3.10+** — `python3 --version`
- **Node 18+** — `node --version`
- **ffmpeg** — only for ingesting new video. `brew install ffmpeg`

### The five commands

```bash
git clone https://github.com/dewangdhakad/ARES.git
cd ARES

# ── terminal 1 · backend ────────────────────────────────
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# ── terminal 2 · frontend ───────────────────────────────
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

### Check it in this order

```bash
curl localhost:8000/api/health      # {"status":"ok",...}
curl -s localhost:8000/api/survivors | python3 -c "import json,sys; print(len(json.load(sys.stdin)),'survivors')"
```

Then in the browser: the header count, the table row count and the map pin
count must be the same number. They are the same list by construction — if
they differ, something is genuinely wrong, not a rounding difference.

### Two gotchas

**`uvicorn backend.main:app` must run from the repo root**, not from inside
`backend/`. The imports are `from backend import ...`; running from inside the
package makes them fail with `ModuleNotFoundError: No module named 'backend'`.

**Port 8000 is hardcoded in the frontend's default.** If you must move it, set
`VITE_API_BASE` when starting Vite:

```bash
VITE_API_BASE=http://localhost:9000 npm run dev
```

That one variable also moves the map tile URL, which is why it exists.

---

## 3. A judge hands you a video

One command. It handles the three things that silently break a dashboard fed
strange footage.

```bash
# weights are NOT in the repo — get them once, from the GitHub Release
#   → models/yolov12s.pt

source .venv/bin/activate
pip install ultralytics            # ~2 GB, only needed for ingest
python tools/ingest_video.py ~/Desktop/judges_video.mp4
```

Then **restart the backend** (it reads `clip_meta.json` at import) and reload
the browser. That is the whole procedure.

### What it does, and why each part matters

| | why |
|---|---|
| **Re-encodes to constant frame rate** | Phone and screen-recorded video is variable-rate. The clock is `frame_id / CLIP_FPS`, which assumes even spacing — VFR makes the log drift away from the video in a way that looks like a log bug. |
| **Detects on the re-encoded file, never the original** | Ultralytics returns boxes in whatever pixel space you feed it. Detect at 3840 wide, play at 1280, and every box and every map pin is wrong by 3×, silently. |
| **Keeps native resolution** (capped at 1920) | Downscaling a 4K clip to "match the demo" can push every person under the size the model can resolve. |
| **Writes `clip_meta.json`** | `backend/config.py` reads it, so `FRAME_WIDTH`, `FRAME_HEIGHT` and `CLIP_FPS` follow the clip. `MIN_TRACK_FRAMES` is derived from `CLIP_FPS`, so the 2.5-second persistence rule stays 2.5 seconds at any rate. |
| **Copies to `frontend/public/`** | That is the copy the browser plays. |

### Read the summary before you demo

```
  raw detections          6,981
  track ids issued          349
  persistence                60 frames (2.5s at 24.0 fps)
  CONFIRMED SURVIVORS        19
  median person height     21.5 px   (context only)
  above 0.70 conf           5.5%   (demo clip: 5.5%)
```

**`above 0.70 conf` is the health check**, benchmarked against the demo clip
rather than an absolute number. A clip much below the reference is flown too
high for this model, or was shrunk too hard by `--max-width`. Median box height
is context only — the demo clip sits at 21.5 px and works fine, so height alone
proves nothing.

### Useful flags

```bash
--seconds 20        # first 20 s only; good for a long video under time pressure
--max-width 1280    # shrink if inference is too slow on the laptop
--fps 24            # force a rate, e.g. if the source declares something absurd
```

### Keep the demo clip recoverable

`ingest_video.py` **overwrites** `detections.json` and both copies of
`demo_clip.mp4`. Before ingesting anything on demo day:

```bash
cp backend/data/detections.json /tmp/ares_demo_detections.json
cp frontend/public/demo_clip.mp4 /tmp/ares_demo_clip.mp4
```

Or just `git checkout backend/data/detections.json frontend/public/demo_clip.mp4`
— both are tracked, so the demo is one command away from restored. Delete
`backend/data/clip_meta.json` too, or config keeps the ingested geometry.

---

## 4. What breaks, and what to do

| Symptom | Cause | Fix |
|---|---|---|
| `{"detail":"Not Found"}` at `localhost:8000` | There is no `/` route. This is correct. | Go to `/api/health` or the frontend at :5173 |
| `ModuleNotFoundError: No module named 'backend'` | uvicorn started from inside `backend/` | `cd` to the repo root |
| Header shows **offline** badge | `/api/config` unreachable | Backend is down. The dashboard is running on `config.js` fallbacks and **saying so** — that is the designed behaviour, not a failure |
| `503 No detections file` | `detections.json` missing | `git checkout backend/data/detections.json` |
| Map pins render, base map grey | Tiles missing or panned outside the cached box | Expected outside the box. Inside it: `python tools/fetch_tiles.py` |
| Video black, controls dead | Codec the browser won't decode | Re-run ingest — it forces h264/yuv420p |
| Survivor count is 0 after ingest | No track lasted 2.5 s | Clip too short, or footage above operating altitude. Check `above 0.70 conf` |
| Counts disagree across panels | Real bug | They are one list by construction; report it |
| `ffmpeg: command not found` | Not installed | `brew install ffmpeg` |
| Ingest: `Weights not found` | `models/` is gitignored | Download `yolov12s.pt` from the GitHub Release |

---

## 5. The offline path

`CLAUDE.md` demo-day constraint 2: **the dashboard must work with the backend
switched off.** Test it, do not assume it.

```bash
# with both running and the dashboard loaded, kill the backend
#   → header shows the offline badge
#   → video keeps playing, overlay keeps drawing
#   → config falls back to frontend/src/config.js
```

Map tiles come from the backend, so they stop when it does. Everything else
keeps running.

**Wifi is the other test.** Tiles are already cached in the repo — 376 of them,
tracked in git — and Leaflet points at the backend rather than at
openstreetmap.org, so the base map survives a dead venue network. Turn wifi off
and confirm, rather than trusting this paragraph.

### The full dry run, worth doing once before the 10th

```bash
git clone <repo> /tmp/ares-dryrun && cd /tmp/ares-dryrun
# ... the five commands ...
# then: wifi off. Then: kill the backend.
```

A clean clone catches the one class of bug nothing else does — a file that
works on your laptop because it never got committed.

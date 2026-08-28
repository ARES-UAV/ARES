# Running the ARES dashboard on your machine

**For Robin — 24 August 2026**

## The short version

**You do not need the model, PyTorch, or Ultralytics to run the dashboard.**

The backend replays a pre-computed detections file. It never runs inference.
That is deliberate — it is why the JSON contract exists, and it means your setup
is three small packages instead of a 2 GB install.

The `.pt` and `.onnx` Dewang sent you are for regenerating detections, which you
only need if you are re-running tracking. Skip them for now. Section B covers
them when you get there.

---

# A. Running the dashboard

## What you need installed

- **Python 3.10 or newer** — check with `python --version` (Windows) or
  `python3 --version` (macOS/Linux)
- **Node.js 18 or newer** — check with `node --version`
- **Git**

## 1. Clone

```bash
git clone <repo-url>
cd ARES
```

## 2. Drop in the three files that are not in git

The repo deliberately does not contain footage or detection output — video and
weights bloat git history permanently. Dewang sends these separately, or they
are attached to a GitHub Release.

Put them exactly here:

```
backend/data/detections.json      ← the important one. Nothing works without it.
backend/data/demo_clip.mp4
frontend/public/demo_clip.mp4     ← same file, second location. Not a mistake.
```

The clip lives in two places because the backend and the frontend each need
their own copy — one serves the playback clock, the other serves the `<video>`
element.

## 3. Backend

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Windows (PowerShell)**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

If PowerShell refuses to run the activate script, that is Windows' execution
policy, not a broken repo:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Three packages, a few seconds. If pip starts downloading torch, you have the
wrong requirements file — that is `ai/requirements.txt` and you do not want it.

**Check it works.** In a browser or a second terminal:

```bash
curl http://localhost:8000/api/survivors
```

You should get a JSON array of 23 survivors. If you get `[]`, `detections.json`
is missing or in the wrong folder.

## 4. Frontend

Leave the backend running. **New terminal:**

```bash
cd frontend
npm install
npm run dev
```

Open the URL it prints, usually `http://localhost:5173`.

---

## When it doesn't work

**Dashboard loads but every panel is empty / zero survivors**
The backend isn't reachable from the frontend. Two possible wirings — check
`frontend/vite.config.js`:

- If there's a `proxy` block pointing `/api` at `localhost:8000`, the backend
  must be running on exactly port 8000.
- If there's a `VITE_API_BASE` or similar env variable, create
  `frontend/.env.local` with `VITE_API_BASE=http://localhost:8000`.

Open the browser devtools Network tab. Failed `/api/...` requests tell you which
one it is immediately.

**Video panel stuck on "Loading clip…"**
`frontend/public/demo_clip.mp4` is missing. Copying it to `backend/data/` only
is the usual mistake — it needs to be in both.

**`Address already in use` on port 8000**
Something else has it. Use `--port 8001` and update the proxy or env variable to
match.

**`uvicorn: command not found`**
The venv isn't activated. Your prompt should start with `(.venv)`.

**`ModuleNotFoundError: No module named 'backend'`**
You're in the wrong directory. `uvicorn backend.main:app` runs from the repo
root, not from inside `backend/`.

---

# B. Regenerating detections (only if you need it)

Needed if you want to re-run tracking — trying BoT-SORT instead of ByteTrack,
or a different input size. **A separate virtualenv**, because this one is ~2 GB
and you do not want it entangled with the light backend env:

```bash
python3 -m venv .venv-ml
source .venv-ml/bin/activate          # Windows: .venv-ml\Scripts\Activate.ps1
pip install -r ai/requirements.txt
```

Put the weights at `models/yolov12s.pt` (or wherever the tool script expects —
check the path constant at the top of the file).

Useful scripts in `tools/`:

| script | what it does |
|---|---|
| `compare_trackers.py` | ByteTrack vs BoT-SORT on the demo clip, reports unique IDs |
| `test_imgsz.py` | re-tracks at 640 / 960 / 1280 and compares |
| `analyse_tracks.py` | tells you how many track IDs are real people |

**Settings that matter and are not defaults:**

```
conf    = 0.18     # deliberately low — tuned for recall, a missed survivor
                   # costs more than a false alarm
max_det = 1000     # NOT the default 300. Scenes routinely exceed 300 people.
imgsz   = 960      # the current detections.json was produced at 960, not 640.
                   # At 640 a 24 px person becomes 12 px and tracking falls apart.
```

If you regenerate, **say so** — the numbers on the dashboard change and everyone
needs to be looking at the same file.

---

# C. What you own

`backend/localize.py` and `backend/priority.py` are yours. What's in the repo now
are stubs built from the formulas in `CLAUDE.md`, written so the dashboard wasn't
blocked waiting. Swap yours in whenever they're ready.

Read `ARES_priority_localize_changes_for_Robin.md` before you do — two changes
were made in those files that alter what values *mean*, not just what they are,
and your versions need to carry them or the defects come back.

**Do not change the JSON input contract.** It touches all three of us:

```json
{"frame_id": 0, "bbox": [x1, y1, x2, y2], "confidence": 0.87, "track_id": 2, "class": 0}
```

If something genuinely needs to change there, flag it rather than changing it.

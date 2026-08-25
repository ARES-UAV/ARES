# Part 8 — The Tools Directory and Every Command

Eight scripts in `tools/`, plus every command you typed to get here.

---

## 1. What `tools/` is for

**Nothing in `tools/` runs during the demo.** These are offline scripts: they
produce artefacts (`detections.json`, `demo_clip.mp4`, cached tiles) or they
answer questions (which input size, which tracker, how fast on device).

That separation is why `requirements.txt` has three packages and
`ai/requirements.txt` has two gigabytes. **The dashboard never imports
Ultralytics.**

Each script is written to be run once and read. They print interpretations, not
just numbers — which matters, because a table of statistics you don't know how to
read is not a measurement.

---

## 2. `survey_visdrone.py` — pick a sequence

```bash
python tools/survey_visdrone.py ~/Downloads/VisDrone2019-VID-val
```

**The problem:** several VisDrone sequences are motorways. A clip full of cars
demonstrates nothing about survivor detection.

**The approach:** the val set ships ground-truth annotations, so the script ranks
sequences by how many *people* are in them — from data, rather than by scrolling
thumbnails.

```
VisDrone annotation columns:
    frame, target_id, x, y, w, h, score, category, truncation, occlusion

Category 1 = pedestrian, 2 = people. Everything else is vehicles and bikes.
```

`MIN_FRAMES = 320` — you need 13 seconds at 24 fps, with headroom.

### The density lesson

**Early advice here was wrong**, and the correction is worth carrying.

The initial instinct was to pick the *densest* sequence — more people looks more
impressive. In practice it made **de-duplication visible as a failure**: with
hundreds of overlapping people, the gap between the tracker's ID count and the
confirmed survivor count became so large it read as a broken system rather than a
working filter.

**Moderate density demonstrates the pipeline better than maximum density.** You
want enough people that clustering means something and few enough that a judge can
count them by eye and see that your number is right.

---

## 3. `build_demo_clip.py` — the artefact producer

```bash
python tools/build_demo_clip.py ~/Downloads/VisDrone2019-VID-val uav0000086_00000_v
```

The single most important script in the repo. Five stages:

### Stage 1 — assemble the clip with ffmpeg

```bash
ffmpeg -y -framerate 24 \
  -pattern_type glob -i 'sequences/*.jpg' \
  -vf "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720" \
  -c:v libx264 -crf 23 -preset fast \
  -pix_fmt yuv420p -movflags +faststart \
  -t 13 demo_clip.mp4
```

| Flag | Meaning |
|---|---|
| `-framerate 24` | Input images become a 24 fps video |
| `-pattern_type glob` | Match `*.jpg` rather than a `%07d` pattern — VisDrone naming varies |
| `scale=…:force_original_aspect_ratio=increase` then `crop` | Fill 1280×720 without distorting, then trim the overflow |
| `-c:v libx264` | H.264, the universally-playable codec |
| `-crf 23` | Quality, 0 (lossless) to 51. 23 is the sensible default |
| `-pix_fmt yuv420p` | **Required** for Safari and QuickTime compatibility |
| `-movflags +faststart` | Moves the metadata index to the front of the file |
| `-t 13` | Thirteen seconds |

**`+faststart` deserves a note.** By default, MP4 metadata sits at the *end* of
the file, so a browser must download the whole thing before it can start playing.
`+faststart` moves it to the front. On a local file it barely matters; if the
video is ever served over a network it is the difference between instant playback
and a long stall. It costs nothing, so it goes on every video this project
produces.

### Stage 2 — verify dimensions, the trap the script exists to avoid

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height -of csv=p=0 demo_clip.mp4
```

```python
if (w, h) != (WIDTH, HEIGHT):
    sys.exit(f"! expected {WIDTH}x{HEIGHT} — every coordinate would be wrong. Stopping.")
```

**This is the most important five lines in `tools/`.** The header comment states
the rule:

> **THE RULE THAT MATTERS:** detection runs on the ASSEMBLED 1280×720 clip, never
> on the original JPEGs. Ultralytics returns boxes in whatever coordinate space
> you feed it. VisDrone frames are usually 1344×756 or 1920×1080 — run on those
> and every box is wrong by that ratio against `FRAME_WIDTH=1280`, **silently**.

A 1920-wide source detected directly would produce boxes scaled 1.5× wrong.
Nothing would crash. Every survivor would land in the wrong place, plausibly.

### Stage 3 — detect and track

```python
model = YOLO(str(WEIGHTS))
model.model.names = {0: "person"}      # YOLOv12s ships as 'human'

results = model.track(
    source=str(CLIP),
    tracker="bytetrack.yaml",   # explicit — 8.4.x defaults to tracktrack
    persist=True,
    conf=0.18,
    max_det=1000,
    stream=True,                # frame by frame, or RAM explodes
    save=True,                  # annotated copy, useful for the demo video
    verbose=False,
)
```

Two comments encode real gotchas:

- **`tracker="bytetrack.yaml"` is explicit** because Ultralytics 8.4.x changed its
  default to `tracktrack`. Relying on a default that moved between versions is how
  you get different results from the same command on two machines.
- **`stream=True`** yields frames one at a time. Without it, every frame's results
  accumulate in memory.

### Stage 4 — extract the densest frame

```python
busiest, count = Counter(d["frame_id"] for d in detections).most_common(1)[0]
```

Saved as `models/test_frame_dense.jpg`, for an honest Pi benchmark. See Part 4.

### Stage 5 — copy to `frontend/public/`

The clip lives in **two places** because the backend serves the playback clock and
the frontend serves the `<video>` element. That is CLAUDE.md constraint 2 — the
video panel must work with the backend switched off.

### What the script tells you at the end

```
EXPECT THE TRACK COUNT TO LOOK TOO HIGH.
At conf 0.18 on real footage you get flicker — a shadow or a bag that
reads person-shaped for one frame gets a fresh ID. That is the price of
the high-recall threshold, and it is what the persistence filter removes.
Write the number down: the before/after is a good demo.
```

That last sentence is good advice. **333 → 23 is a demo beat**, not an
embarrassment.

---

## 4. `test_imgsz.py` — the input-size sweep

```bash
python tools/test_imgsz.py
```

Re-tracks the clip at 640, 960 and 1280, and reports detections, unique IDs,
median track length, median confidence, and detections per frame.

**How to read it**, straight from the script:

> All three should move together if size is the problem:
> - unique IDs **DOWN** (fewer identities for the same people)
> - median track length **UP** (identities holding across more frames)
> - median confidence **UP** (the model is surer about what it sees)
>
> If IDs barely move but confidence rises, size was not the limiting factor and
> the tracker is the thing to change. If nothing moves, the footage is simply too
> high for this model and the answer is a different clip — not a parameter.

**That last branch is the valuable one.** It tells you when to stop turning knobs.
A tool that only reports numbers lets you tune forever; a tool that tells you what
the numbers rule out ends the search.

Your result: 960 won. See Part 3.

---

## 5. `compare_trackers.py` — ByteTrack vs BoT-SORT

```bash
python tools/compare_trackers.py
```

Runs both with **identical detection settings**, so any difference is purely
identity-holding.

The output includes one metric worth knowing:

> **"highest ID issued"** — a number far above the unique count means the tracker
> opened and abandoned many candidate tracks. A direct signal of how much it is
> struggling with this footage.

And the closing instruction is the honest one:

> Scrub the clip and watch ONE person. Does their ID stay the same when someone
> walks in front of them? **That is the test that matters, and no summary number
> can answer it for you.**

---

## 6. `analyse_tracks.py` — are these track IDs real people?

```bash
python tools/analyse_tracks.py
```

Three sections:

1. **The persistence curve** — survivors remaining at each `min_frames` threshold
2. **Track length distribution** — a histogram
3. **Are the short tracks real or noise?** — the flicker / frame-edge / ID-switch
   classification from Part 3

Its verdict logic:

```python
if conf_gap > 0.08:
    "Short tracks are notably LOWER confidence — consistent with flicker.
     Persistence filtering is the right fix."
else:
    "Short tracks have SIMILAR confidence — probably NOT false positives.
     Filtering them discards real people."
```

**This is the script that justified `MIN_TRACK_SECONDS`.** Without it, 2.5 seconds
would be a guess. With it, 2.5 seconds is a response to a measurement: short
tracks at mean confidence 0.42 against 0.52, only 7% at the frame edge.

And it ends by telling you the numbers are not the ground truth:

> Scrub the clip and count the people you can actually see in one frame. Compare
> that to the numbers above. **Your eyes are the ground truth here.**

---

## 7. `benchmark.py` — honest timing

Covered fully in Part 4. Warm-up runs discarded, median over 30 runs, best/worst
printed, stage breakdown reported.

```bash
python tools/benchmark.py models/yolov12s.pt 960 models/test_frame_dense.jpg
```

---

## 8. `fetch_tiles.py` — offline map tiles

```bash
python tools/fetch_tiles.py
```

**Why:** CLAUDE.md constraint 3 — map tiles need internet and venue wifi fails.
*Discovering that on 5 September is not a plan.*

Downloads a 1 km box centred on the GPS origin, at zoom 14 through 19, into
`backend/data/tiles/`. The backend then serves them from `/tiles/{z}/{x}/{y}.png`
and Leaflet never talks to openstreetmap.org during the demo.

### Two details worth knowing

**The origin is read from `backend/config.py`, not restated.** Move the demo
clip's origin, re-run, and the bundled tiles follow.

**The box must contain the flight track, not just its start.** At 5 m/s a clip
would have to run past 100 seconds before it left a 1 km box — but a longer clip
or faster track needs a bigger `--km`. The tool prints the box it used, so the
number is checkable rather than assumed.

### Being a good citizen

OSM's tile servers are **donated infrastructure**, and its usage policy asks bulk
downloaders to identify themselves and go easy. So the script sends a User-Agent
naming the project and its repo, makes one request at a time with a delay, and
never re-requests a tile already on disk.

> The default box is a few hundred tiles. **Do not point this at a city.**

That is not just etiquette — it is the kind of thing that gets an IP blocked, two
days before a demo.

---

## 9. `make_fixture.py` — the scaffolding

```bash
python tools/make_fixture.py > backend/data/fixture_detections.json
```

Generates synthetic detections so the frontend could be built before real footage
existed. Deterministic (`SEED = 7`), 300 frames, 9 survivors, one tight cluster to
give the priority scorer real signal.

Its own docstring is unambiguous:

> **WHAT THIS IS NOT.** This is NOT demo data. These boxes are generated by
> arithmetic, not by the detection model. **Never load this file for a demo, a
> screenshot, or the recorded video. Delete it once real detections exist.**

**You hit this exact trap.** After producing real detections, the dashboard still
showed 9 survivors — because `config.py` still pointed at
`fixture_detections.json`. The fix was one `sed`, but the lesson is that a fixture
that looks plausible is more dangerous than one that looks obviously fake.

---

## 10. Shell commands

### Navigation and files

```bash
pwd                     # where am I
ls -la                  # list, including hidden files, with detail
cd ~/Project/ARES       # change directory; ~ is your home
cp source dest          # copy
mv old new              # move or rename
rm file                 # delete (no undo, no trash)
rm -rf directory        # delete a directory and everything in it. Be careful.
mkdir -p a/b/c          # create nested directories
cat file                # print a file
head -20 file           # first 20 lines
du -sh directory        # how big is this
```

### The zsh gotchas you hit

**`?` is a glob character.** A comment containing `?` in a command line made zsh
try to match filenames. Quote anything with `?`, `*` or `[]`.

**`python` vs `python3`.** On macOS, `python` may not exist. Use `python3`, or
activate a venv where `python` is defined.

**Pasting Python into zsh.** Multi-line Python at a shell prompt gets interpreted
as shell. Use a heredoc, a `-c` string, or a file.

---

## 11. Virtual environments

```bash
python3 -m venv .venv          # create
source .venv/bin/activate      # activate (macOS/Linux)
.venv\Scripts\Activate.ps1     # activate (Windows PowerShell)
deactivate                     # leave
```

Your prompt shows `(.venv)` when active.

**Why:** different projects need different package versions. A venv is an isolated
package directory so ARES's `ultralytics>=8.4.126` does not fight another
project's pinned older version.

**You have two, deliberately:**

- `.venv` — the backend. Three packages, seconds to install.
- `.venv-ml` — Ultralytics, torch, ONNX. About 2 GB.

```bash
pip install -r requirements.txt        # backend
pip install -r ai/requirements.txt     # ML
pip list                               # what's installed
```

### The macOS `--break-system-packages` note

Homebrew Python marks itself "externally managed" and refuses global installs.
**The right answer is a venv, not the override flag.** If you find yourself
reaching for `--break-system-packages`, you have forgotten to activate.

---

## 12. Git

### The everyday loop

```bash
git status                     # what changed
git diff                       # show the changes
git add .                      # stage everything
git add path/to/file           # stage one file
git commit -m "message"        # record staged changes
git push                       # send to GitHub
git pull                       # fetch and merge
git log --oneline -10          # recent history
```

### `.gitignore`

Patterns for files git should never track. Yours excludes:

| Pattern | Why |
|---|---|
| `*.pt`, `*.onnx` | **Git stores every version forever.** A 22 MB checkpoint committed five times is 110 MB that can never be reclaimed without rewriting history. Weights go to GitHub Releases |
| `*.mp4` | Same, worse |
| `detections*.json` | Regenerated by running the model |
| `node_modules/` | ~200 MB, reinstallable from `package.json` |
| `.venv/`, `venv/` | Environments are rebuilt, not shared |
| `.env`, `*.key`, `*.pem` | **Secrets. Never.** |

**The critical caveat, written at the top of your own file:**

> Adding a pattern here does NOT untrack files git already tracks. It only stops
> NEW ones.

```bash
git rm --cached path/to/file       # untrack, keep on disk
```

### The 182 MB disaster

```
remote: error: File .venv-ml/lib/python3.12/site-packages/torch/lib/libtorch_cpu.dylib
        is 322.26 MB; this exceeds GitHub's file size limit of 100.00 MB
```

**What happened:** `.gitignore` listed `.venv/` but not `.venv-ml/`. The pattern
`.venv/` does not match `.venv-ml/`. The whole 2 GB ML environment got staged.

**Why `git rm --cached` alone would not have fixed it:** the blob is still in an
earlier commit's tree, and a push sends *every object* in the history being
pushed. GitHub's pre-receive hook scans all of them. You would get the identical
rejection.

**The two real fixes:**

```bash
# If every offending commit is unpushed — the easy case
git reset --soft origin/main    # uncommit, touching no files on disk
git rm -r --cached .venv-ml     # unstage the venv
git commit -m "..."
git push
```

```bash
# If it is already in pushed history — rewrite
brew install git-filter-repo
git filter-repo --path .venv-ml --invert-paths --force
git push -f
```

**The lesson worth generalising:** git history is append-only by default.
Something committed once is committed forever unless you rewrite. Check what you
are about to commit *before* you commit it:

```bash
git status                     # look at this every time
du -sh .                       # and this, if the repo feels heavy
```

---

## 13. Running the system

```bash
# Terminal 1 — backend, from the repo root
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install       # once
npm run dev
```

| npm script | What it does |
|---|---|
| `npm run dev` | Vite dev server with hot reload |
| `npm run build` | Production bundle into `dist/` |
| `npm run preview` | Serve the built bundle |
| `npm run lint` | Run oxlint |

---

## 14. Inspecting the API

### The interactive docs

```
http://localhost:8000/docs
```

FastAPI generates this from your type annotations. Every endpoint, every schema,
and a "Try it out" button. **Open this during the demo if a judge asks what the
API looks like** — it is free credibility and you did not write a line of it.

### curl plus a Python one-liner

`curl` fetches; Python does the analysis. This pattern ran throughout the
diagnostics:

```bash
curl -s localhost:8000/api/survivors | python3 -c "
import json, sys
s = json.load(sys.stdin)
print(len(s), 'survivors')
print(json.dumps(s[0], indent=2))
"
```

| Flag | Meaning |
|---|---|
| `-s` | Silent — no progress meter polluting the pipe |
| `\|` | Pipe stdout into the next command |
| `python3 -c "..."` | Run the string as a program |
| `sys.stdin` | The piped input |

### The ones that found real bugs

**Field discovery** — when a guess about the schema was wrong:

```bash
curl -s localhost:8000/api/events | python3 -c "
import json, sys
from collections import Counter
ev = json.load(sys.stdin)
print('keys', sorted(ev[0].keys()))
for k in ev[0]:
    vals = {str(e.get(k)) for e in ev}
    if 2 <= len(vals) <= 12:
        print(f'  {k}: {dict(Counter(str(e.get(k)) for e in ev))}')
"
```

This found that the event discriminator was `kind`, not `type` — after a first
attempt returned `{None: 65}`.

**The clustering sweep** that showed the radius couldn't discriminate:

```bash
curl -s localhost:8000/api/survivors | python3 -c "..."
# radius   3 m:  8 groups
# radius  15 m:  1 group
```

**The lesson:** when a query returns something surprising, **make the next query
self-describing.** Print the keys, print the value histogram, print one whole
record. Guessing twice costs more than introspecting once.

---

## 15. ffmpeg and ffprobe

```bash
# Inspect
ffprobe -v error -show_entries stream=width,height,r_frame_rate \
        -of default=noprint_wrappers=1 clip.mp4

# Extract one frame
ffmpeg -i clip.mp4 -vf "select=eq(n\,240)" -vframes 1 -q:v 2 frame.jpg

# Re-encode for compatibility
ffmpeg -i in.mp4 -c:v libx264 -pix_fmt yuv420p -movflags +faststart out.mp4
```

**The two flags to always include on any video this project produces:**

- `-pix_fmt yuv420p` — Safari and QuickTime will not play some other pixel formats
- `-movflags +faststart` — metadata at the front

---

## 16. The command reference card

```bash
# ── Environment ────────────────────────────────────────────────
source .venv/bin/activate                   # backend env
source .venv-ml/bin/activate                # ML env

# ── Run ────────────────────────────────────────────────────────
uvicorn backend.main:app --reload --port 8000
cd frontend && npm run dev

# ── Produce artefacts ──────────────────────────────────────────
python tools/survey_visdrone.py ~/Downloads/VisDrone2019-VID-val
python tools/build_demo_clip.py ~/Downloads/VisDrone2019-VID-val <sequence>
python tools/fetch_tiles.py

# ── Investigate ────────────────────────────────────────────────
python tools/analyse_tracks.py
python tools/test_imgsz.py
python tools/compare_trackers.py
python tools/benchmark.py models/yolov12s.pt 960 models/test_frame_dense.jpg

# ── Inspect the API ────────────────────────────────────────────
open http://localhost:8000/docs
curl -s localhost:8000/api/survivors | python3 -m json.tool | head -40
curl -s localhost:8000/api/config    | python3 -m json.tool

# ── Git ────────────────────────────────────────────────────────
git status && du -sh .                      # BEFORE every commit
git add . && git commit -m "..." && git push
gh release create v0.9-demo <files> --notes "..."
```

---

## What to take from this part

- `tools/` runs offline and never during the demo. That is why the backend needs
  three packages.
- **`build_demo_clip.py` verifies the clip is 1280×720 before detecting**, because
  detecting on the wrong resolution silently scales every coordinate.
- `analyse_tracks.py` is what turned 2.5 seconds from a guess into a response to a
  measurement.
- `fetch_tiles.py` is polite to donated infrastructure on purpose.
- **`git status && du -sh .` before every commit.** The 182 MB push failed because
  `.venv/` doesn't match `.venv-ml/`.
- When a query surprises you, make the next one self-describing.

**Next:** Part 9 — every decision, every alternative, and every mistake.

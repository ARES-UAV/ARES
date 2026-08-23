# ARES Dashboard — Build Order

For Dewang. Build in this order. Each stage has a prompt you can paste into Claude Code and a test that tells you the stage is finished.

**The rule for the whole build:** never start a stage until the previous stage's test passes. A half-finished panel is worse than a missing one, because you cannot tell which part is broken.

---

## Stage 0 — Make one number travel from backend to browser

This is the most important stage and it looks like the least impressive. You are proving the wire works before you put anything valuable on it. Beginners skip this, build three panels, then spend two days finding out the fetch was misconfigured the whole time.

### 0.1 — Scaffold

```
Set up the repo structure described in CLAUDE.md: a backend/ folder with a
FastAPI app, and a frontend/ folder with Vite + React + Tailwind. Add a
requirements.txt and a README with the two commands needed to run each side.
Don't build any features yet — just the skeleton, and confirm both start.
```

### 0.2 — Get a fixture in place

Run `python tools/make_fixture.py > backend/data/fixture_detections.json`.

That gives you 2,027 detections across 9 tracks so you can build the UI today, without waiting for footage. It is development scaffolding only — read the demo footage policy in CLAUDE.md.

### 0.3 — One endpoint, one number

```
In backend/main.py add a GET /api/detections endpoint that loads
backend/data/fixture_detections.json and returns it. Define the record shape as
a Pydantic model in backend/schemas.py, matching the contract in CLAUDE.md
exactly. Enable CORS for the Vite dev server.

Then in the frontend, replace the default App with a page that fetches that
endpoint on load and displays two numbers: total detections, and unique
track_ids excluding -1.
```

**Done when:** your browser shows **2027 detections** and **9 survivors**. It will be ugly. That is correct — do not style it yet.

---

## Stage 1 — Video player, playback clock, bounding boxes

Build this first among the panels, for two reasons. It is the single most convincing thing on screen — if only one panel worked, this is the one you would want. And the **playback clock is the spine of the whole dashboard**: every other panel answers "what is true at frame N". Retrofitting a clock later means rewriting everything.

You need a video file. Any aerial clip works for development — grab a free drone clip from Pexels or Pixabay and put it in `backend/data/`. The fixture is sized for 1280×720 at 30 fps.

```
Build the video panel. A <video> element playing backend/data/demo_clip.mp4,
with a canvas overlaid on top at the same size.

Derive the current frame from the video's currentTime and the clip's fps, and
hold it in a single piece of React state that other components will read —
this is the app's playback clock, so put it somewhere shared, not inside the
video component.

On each frame, draw the bounding boxes for that frame_id onto the canvas.
Label each box with its track_id. Scale box coordinates from the source
resolution to the displayed element size.

Survivor boxes must NOT be red — red is reserved for hazards and high priority.
```

**Done when:** boxes track people as the video plays, and stay aligned when you resize the window.

---

## Stage 2 — Stat header

Cheap to build, and it fixes the design review's number-one complaint: counts that disagree between sections.

Do it now, not later, because it forces you to decide **where counts live**. Derive every number from the same shared state the clock uses. If two components each compute their own count, they will drift, and a judge will spot it.

```
Add a header bar across the top with four stats, all derived from the shared
playback state so they can never disagree with the other panels:

  - Raw detections in the current frame
  - Unique survivors tracked so far (distinct track_ids up to this frame, -1 excluded)
  - On-device FPS — a constant from the config module for now, labelled with the device
  - "Detection Mode: High Recall" indicator

Label the two counts distinctly enough that nobody could confuse them.
```

**Done when:** the numbers move as the video plays and match what you can count on screen.

---

## Stage 3 — Map

Third because it carries the most risk. Map tiles need internet, and venue wifi fails. Finding that out on 5 September is how demos die — finding out now leaves you two weeks to cache tiles or swap in a static image background.

Localization is Robin's `localize.py`. If it is not ready, stub it — the formula is five lines and it is in CLAUDE.md.

```
Add a Leaflet map panel with OpenStreetMap tiles.

Create backend/localize.py implementing the pixel→GPS conversion from CLAUDE.md,
with altitude, FOV and origin lat/lon as constants in a single config module.
Add a GET /api/survivors endpoint returning one record per unique track_id with
its latest position converted to lat/lon.

Plot each survivor as a marker. Use the same non-red survivor colour as the
video overlay. Clicking a marker highlights that track_id in the other panels.
```

**Done when:** markers appear in plausible positions and clicking one cross-highlights.

Then immediately test it with wifi off, and write down what you see. That result decides whether you need cached tiles.

---

## Stage 4 — Survivor table with priority ranking

```
Add a table listing every unique survivor: track_id, first seen frame, detection
confidence, lat/lon, and priority score.

Create backend/priority.py with a transparent weighted formula — confidence,
cluster size (survivors within N metres), and hazard proximity. Keep the weights
in the config module. A judge will ask how this works, so it must be explainable
in one sentence.

Sort by priority descending. Selecting a row highlights that survivor on the map
and in the video overlay.
```

**Done when:** the table's row count equals the header's tracked-survivor count. If they differ, stop and fix it — that exact mismatch was the first mockup's biggest flaw.

---

## Stage 5 — The design review fixes

Everything works by now. This is where it stops looking like a student project.

```
Polish pass:
  - Give survivors a dedicated colour, distinct from hazard red and priority red
  - Set the mission date to the current date, not a placeholder
  - Add playback controls: play/pause, scrub, and a frame counter
  - Make the layout hold together at 1280px wide (projector resolution)
  - Add a loading state and an error state for when the backend is unreachable
```

Then the fallback that matters on the day:

```
Add a static mode: if the backend is unreachable, load detections from a JSON
file bundled with the frontend and run the whole dashboard from that. Every
panel must work in this mode. Show a small badge when it is active.
```

**Done when:** you kill the backend, reload, and the dashboard still runs.

---

## Stage 6 — Only if the above is finished

Priority routes annotated on the map · thermal view (must look genuinely different, not a filtered copy) · hazard overlays once the AIDER classifier exists.

Do not start any of these before Stage 5 passes.

---

## Running order against the calendar

| | Stage | Target |
|---|---|---|
| 1 | Stage 0 — walking skeleton | 24 Aug |
| 2 | Stage 1 — video + clock + boxes | 26 Aug |
| 3 | Stage 2 — stat header | 27 Aug |
| 4 | Stage 3 — map | 29 Aug |
| 5 | Stage 4 — table + priority | 31 Aug |
| 6 | Stage 5 — polish + offline fallback | 2 Sept |
| 7 | Real detections swapped in, full rehearsal | 3 Sept |
| 8 | Ujjaini records the demo video | 4 Sept |

Stage 5 landing on 2 September is deliberate. It leaves two days of slack, and you will need them.

---

## Working with Claude Code

- **One stage per session.** Run `/clear` between stages so context stays clean.
- **Use plan mode for Stages 3 and 4.** Let it propose an approach before it writes code.
- **Run the app after every stage.** Do not stack three stages of unverified code.
- **Commit after every passing test.** `git commit -m "stage 2: stat header"` — so a bad session is one `git checkout` away from undone.
- When something breaks, paste the actual error text. Describing it from memory wastes both your turns.

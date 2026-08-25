# Part 3 — Tracking, De-duplication, and the Bugs

This part is the most useful one in the handbook, because it is the only place
where you can show a judge that you **diagnosed** something rather than
configured it.

---

## 1. Why tracking exists

Detection has no memory. Frame 11 and frame 12 are two independent questions.

So if you count detections across a clip:

```
7,081 detections over 320 frames
```

That is not 7,081 people. It is roughly 23 people, each detected in many frames.
Without identity, the count is meaningless.

**Tracking assigns each person a persistent `track_id`.** Then:

```python
survivor_count = len(set(d["track_id"] for d in detections))
```

The number of distinct IDs is the de-duplicated count. That single line is the
reason tracking is in the pipeline.

---

## 2. How a tracker works

The general shape, which is enough to explain it:

1. **Predict.** For each existing track, guess where it will be in the next frame,
   usually with a **Kalman filter** — a standard technique that maintains a
   position-and-velocity estimate and updates it as observations arrive.
2. **Associate.** Match the new frame's detections to the predicted positions.
   This is an assignment problem, typically solved with the **Hungarian
   algorithm**, scoring candidate matches by IoU (and sometimes appearance).
3. **Update.** Matched tracks take the new position. Unmatched detections start
   new tracks. Unmatched tracks are kept alive briefly (in case of a short
   occlusion) and then retired.

### ByteTrack

The default in Ultralytics and what you use.

Its trick is in the name: most trackers throw away low-confidence detections
before association. ByteTrack keeps them and does association in **two passes** —
first match high-confidence detections, then try to match the *leftover* tracks
against the low-confidence detections.

Why that helps: when a person is partially occluded, their detection confidence
drops. A tracker that discards low-confidence boxes loses them at exactly the
moment they most need holding. ByteTrack recovers them.

This pairs unusually well with your `conf=0.18` choice, which is worth pointing
out — the low threshold produces exactly the marginal detections ByteTrack's
second pass is designed to use.

### BoT-SORT

The alternative. Adds **camera motion compensation** and optional **re-
identification** (appearance features, so a person who disappears and reappears
can be matched by how they look rather than only where they are).

Roughly 30% slower. More robust to occlusion.

### Which you use, and why the speed doesn't matter

```python
model.track(source=clip, tracker="bytetrack.yaml", persist=True)
```

`tools/compare_trackers.py` runs both on your clip and reports unique ID counts
under identical detection settings, so any difference is purely the tracker's
ability to hold identity.

**Critically: tracker speed is irrelevant to this project.** Tracking runs once,
offline, to produce `detections.json`. Nothing in the demo tracks in real time. If
BoT-SORT holds identities better, its 30% cost buys you a better number for free.

---

## 3. The bug: 333 IDs for 23 people

### What you saw

You ran the model over real VisDrone footage, opened the dashboard, and the map
showed a dense cluster of survivors that could not possibly correspond to what
was in the video. You said:

> "detecting is working fine but i guess tracking is not as how can be so many
> people be there and see the cluster in map"

And later, decisively:

> "whom is he tracking i cant find a single person whom the model tracking
> correctly"

That is the right instinct. **Your eyes are the ground truth.** No summary
statistic overrides "I watched the clip and there aren't 333 people in it."

### Wrong diagnosis #1 — camera motion

The first hypothesis was that the drone was moving fast enough that boxes jumped
between frames, breaking IoU-based association.

**You corrected it:** *"no the video is smooth so sudden jump."*

Measured: **1.4 pixels of movement per frame.** Camera motion was not the cause.
The hypothesis was reasonable and the measurement killed it, which is how this is
supposed to work.

### Wrong diagnosis #2 — duplicate boxes

Second hypothesis: NMS was failing and each person was getting several
overlapping boxes, each spawning its own track.

Measured: **1.12 boxes per cluster.** Essentially no duplication. Also wrong.

### The actual cause — box size relative to input resolution

The clip is 1280 wide. Detection was running at `imgsz=640`.

**Every frame was being halved before the model saw it.** A person 24 pixels tall
in the source arrived at the network as 12 pixels. That is below the size the
model can resolve reliably, so detections **flickered** — present in frame 40,
absent in 41, back in 42.

And here is the mechanism that turns a detection problem into a tracking problem:

> A tracker cannot hold an identity across detections that keep vanishing. Every
> time a person flickered out for more than the tracker's patience, their track
> was retired. When they flickered back, they were a *new person* with a *new ID*.

One person walking across the frame could pick up five, ten, fifteen IDs.

### The fix, and the measurement that proved it

`tools/test_imgsz.py` re-ran tracking at three input sizes:

| imgsz | detections | unique IDs | median track length | median confidence |
|---|---|---|---|---|
| 640 | 5,502 | 350 | — | — |
| **960** | **7,081** | **333** | — | — |
| 1280 | 7,050 | 345 | — | — |

The script tells you what pattern to look for, and this is the interpretive part
worth understanding:

- **Unique IDs down** — fewer identities for the same people
- **Median track length up** — identities holding across more frames
- **Median confidence up** — the model is surer about what it sees

All three moving together means size was the limiting factor. If IDs barely move
but confidence rises, size wasn't the problem and the tracker is. If nothing
moves, the footage is simply flown too high for this model and the answer is a
different clip, not a parameter.

960 won. `DETECTION_IMGSZ = 960` in config, and it ships to the dashboard.

### The related field finding: 40 metres

Recorded in `experiments/MODEL_SELECTION.md`: **above roughly 40 m altitude a
1.7 m person spans fewer than 24 px at 640 px input**, which is where detection —
not the localization maths — becomes the limiting factor.

This is a genuinely good thing to state in the pitch. It is an honest, measured
operating envelope rather than a claim that the system works at any altitude.

---

## 4. Persistence filtering — 333 to 23

Fixing `imgsz` took 350 IDs to 333. Still not 23.

The remaining gap is not a bug. It is **the price of `conf=0.18`.**

### What is in those 333

At a low confidence threshold, the detector reports things that are person-shaped
for a moment — a shadow, a bag, a patch of rubble that briefly resembles a torso.
The tracker dutifully assigns each one an ID.

`tools/analyse_tracks.py` exists to sort them into three categories, because they
need different fixes:

| Category | Signature | Fix |
|---|---|---|
| **Flicker** | Short, **low** confidence, anywhere in frame | Persistence filtering |
| **Frame edge** | Short, **normal** confidence, near the boundary | *Not a false positive* — a real person entering or leaving. Filtering these loses real people |
| **ID switch** | Medium length, normal confidence, mid-frame | Persistence does **not** fix this. Needs a better tracker, or honest disclosure |

Telling them apart is what decides whether persistence is even the right lever.

### What the measurement said

On your clip:

- Short tracks: **mean confidence 0.42**, against **0.52** for long tracks
- Only **7%** of short tracks start or end at the frame edge

Low confidence, mid-frame, gone in a frame or two. **That is flicker, not people
walking out of shot.** Persistence filtering is the correct fix, and lowering the
recall threshold instead would cost real survivors.

### The rule

```python
MIN_TRACK_SECONDS: float = 2.5
MIN_TRACK_FRAMES: int = int(MIN_TRACK_SECONDS * CLIP_FPS)
```

> A track is a confirmed survivor once it has appeared in at least
> `MIN_TRACK_FRAMES` frames.

333 tracks in; **23 clear 2.5 seconds.**

### Why a duration, and not a frame count

This is the subtlest idea in your codebase and it is worth being able to explain,
because it started as a mistake.

An early version of Robin's build guide said `min_frames = 3`. That was wrong —
not the value, **the unit**.

The same rule has to hold in two places running at wildly different rates:

| Context | Rate | 2.5 seconds is… |
|---|---|---|
| The demo clip | 24 fps | **60 frames** |
| Raspberry Pi 4, CPU | ~1.5 fps | **3 frames** |

A hardcoded `60` would mean 2.5 s on the clip and **40 seconds** on the Pi, which
would reject every survivor in the flight. A hardcoded `3` would mean 2.5 s on the
Pi and **an eighth of a second** on the clip, which filters nothing.

Neither number is wrong. The unit is. **"Seen for two and a half seconds" is the
rule**, and the frame count is whatever that works out to at the rate actually
being processed.

### The floor

```python
def min_track_frames() -> int:
    return max(1, config.MIN_TRACK_FRAMES)
```

`int()` truncates. At a slow enough frame rate, `int(2.5 * 0.3)` is `0`. And a
threshold of `0` makes `frames[threshold - 1]` read `frames[-1]` — the **last**
element — which would confirm every track at the frame it was last seen.

That is a silent, plausible-looking inversion: no crash, no error, just a
dashboard that is subtly and confidently wrong. Flooring at 1 makes the
degenerate case a no-op instead. The rule stops applying at rates that slow,
which is the honest behaviour: 2.5 seconds of evidence is not available in under
one frame.

### Confirmation is an *event with a time*

This is the part that makes the dashboard honest during playback rather than only
at the end.

```python
ordered = sorted(frames)
confirmed[track_id] = ordered[threshold - 1]
```

A track first seen at frame 100 and confirmed at frame 160 **is not a survivor at
frame 130.** Confirming it there would count evidence the clip has not shown yet,
and the header's survivor count would run ahead of the footage underneath it.

That is the one thing a replay dashboard must never do. So `confirmation_frames`
returns not just *which* tracks are confirmed, but *when* — the frame their
`MIN_TRACK_FRAMES`-th detection landed on.

### A subtlety you will be asked about

Confirmation counts **detections, not elapsed time**.

Track 1409 on your clip: `first_frame` 181, `confirmed_frame` 306. That is 125
frames — **5.2 seconds** — under a constant named `MIN_TRACK_SECONDS = 2.5`.

Why? It is only detected in 65 of its 131 frames. It took twice as long in
wall-clock to accumulate 60 sightings.

Counting evidence is the better criterion — a track detected 60 times is
well-evidenced regardless of how long it took. But **the constant's name is
misleading**, and if a judge times it against the clip they will notice. Either
rename it or do not put it on screen.

### What persistence does NOT fix

**ID switches.** One person picks up a second ID after an occlusion. Both halves
persist past 2.5 seconds, so both are confirmed, and the count is one too many.

Persistence cannot fix this — both fragments are well-evidenced. The options are a
better tracker (BoT-SORT) or stating the limitation.

**Your dashboard states it.** That is the right call, and "here is a limitation we
know about and can quantify" is a better answer than a system that appears to have
none.

### Where the filter runs, and why that matters

The filter runs **server-side, on the way out.** It never touches
`detections.json`.

- `/api/detections` still serves every record
- The video overlay still draws every box
- `/api/survivors` applies the filter

The raw file stays complete because it is the model's actual output. Confirmation
is a **display decision**, not an edit to the model's output. If it edited the
file, you could no longer honestly say the detections are unmodified model output.

And it runs **before** localization rather than after, because `cluster_size`
counts how many survivors are nearby — and a flicker that lasted two frames is
not a survivor standing next to anyone.

---

## 5. The three counts on the dashboard

All three are shown, labelled, because the gaps between them are informative:

| Count | Source | Value |
|---|---|---|
| Raw detections in this frame | `detectionIndex.byFrame` | varies |
| Unique track IDs so far | `uniqueTracksThrough()` | up to 333 |
| **Confirmed survivors** | `length` of `/api/survivors` | **23** |

Note the asymmetry in `frontend/src/detectionIndex.js`: the first two are computed
in the frontend, the third **deliberately is not**. It is the length of the array
the table renders as rows.

That is rule 2 from Part 0 in action. If the frontend counted survivors itself,
you would have two calculations of one number, and they would eventually disagree.
Instead there is one number, used twice. **They cannot disagree because there is
nothing to disagree.**

---

## 6. What you would improve

**1. Switch to BoT-SORT if ID switches dominate.** You have `compare_trackers.py`
— run it, and if BoT-SORT produces meaningfully fewer IDs, take it. The 30% cost
is free here.

**2. Re-identification features.** Appearance-based matching would survive longer
occlusions. Heavier, and needs a re-ID model.

**3. Track interpolation.** Fill short gaps by interpolating between the last and
next detection, so a two-frame flicker doesn't retire a track at all.

**4. A ground-truth count.** Manually count people in a few frames of the demo
clip and compare against the confirmed count. That turns "23 seems right" into a
measured accuracy figure, and it is the single most valuable thing you could add
before the 5th if you have a spare hour.

---

## What to take from this part

- Detection has no memory; tracking supplies identity; the ID count is the
  de-duplicated survivor count.
- **333 IDs happened because `imgsz=640` halved a 1280 clip and detections
  flickered.** Two hypotheses were measured and rejected before the right one.
- Persistence filtering (2.5 s) takes 333 to 23, and it is expressed as a
  **duration** because 60 frames and 3 frames are the same rule at different
  rates.
- Confirmation has a *time*, so the count never runs ahead of the footage.
- ID switches remain, and the dashboard says so.

**Next:** Part 4 — getting the model onto a Raspberry Pi, and why ~1 FPS is a
defensible number rather than an embarrassing one.

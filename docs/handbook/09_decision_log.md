# Part 9 — Decision Log

Every significant choice in ARES, the alternatives that were available, and why
this one won. Then the mistakes — including the ones that got as far as being
written into the code before being caught.

**Read the mistakes section.** A judge who believes you made no wrong turns
believes you did not do the work.

---

# PART A — The decisions

## A1. Detection model: YOLOv12s

**Alternatives:** YOLOv8n/s, YOLOv11, YOLOv10, RT-DETR, Faster R-CNN, SSD.

**Why YOLOv12s:**
- Ultralytics-native, which means `.track()`, `.export()` and `.val()` all work
  without integration effort
- YOLO12s scores 48.0 mAP50-95 on COCO at 9.3 M parameters
- `s` is the size where edge deployment is plausible and small-object accuracy is
  still acceptable — `n` loses too much on tiny aerial targets, `m` and up are too
  slow for a Pi 4

**Why not Faster R-CNN:** two-stage, far too slow for edge.
**Why not RT-DETR:** transformer detector, heavier, less mature tooling.
**Why not YOLOv8n:** you compared them directly — `experiments/MODEL_SELECTION.md`
records that the decision was resolved on measured numbers, not preference.

**The known risk:** YOLOv12 trades some speed for accuracy versus v11. On a Pi
that trade needs verifying. It has not been yet — see A21.

---

## A2. Combined C2A + VisDrone, one `person` class

**Alternatives:** either dataset alone; both kept as separate classes; add COCO
person images.

**Why combined:** C2A gives disaster context but composited imagery; VisDrone
gives real aerial capture but ordinary pedestrians. Neither alone is the
deployment distribution; together they span it. **C2A's own paper confirmed
combining beat keeping them separate.**

**Why one class:** the task only needs "is this a person." Merging categories
means every human example trains the same class, which matters enormously with a
small dataset. And a model confusing two person-like classes produces a confusing
count; one class cannot.

---

## A3. Confidence threshold 0.18

**Alternative:** the default 0.5, or anything between.

**Why:** the cost function is asymmetric. A false alarm costs a rescuer thirty
seconds; a missed survivor cannot be recovered.

**Measured** at 960 px on the combined val split: recall **0.824 at 0.18**
against **0.775 at the F1-optimal 0.37** — about 3 extra false alarms per
additional survivor found. Forty-nine more
people found per thousand present.

**Chosen from the PR curve**, not guessed — `PR_curve.png` from the validation
run.

**The cost, stated honestly:** more false positives, which is exactly why the
persistence filter exists (A7). The two decisions are halves of one design.

---

## A4. `max_det = 1000`

**Alternative:** the default 300.

**Why:** at 300, a frame with 400 people silently keeps the 300 highest-confidence
detections. No warning. And it discards the **lowest-confidence** ones — which in
a disaster scene are exactly the partially-buried people you most need.

Dense VisDrone scenes routinely exceed 300. The cost of 1000 is negligible.

---

## A5. `imgsz = 960`

**Alternatives:** 640 (default), 1280.

**Why:** chosen from a measured sweep over the actual clip.

| imgsz | detections | unique IDs |
|---|---|---|
| 640 | 5,502 | 350 |
| **960** | **7,081** | **333** |
| 1280 | 7,050 | 345 |

960 finds the most and fragments them into the fewest identities. 1280 costs more
inference for slightly worse tracking.

**Inference speed did not enter the choice**, because this runs once, offline. The
on-device question is separate and answered by `DEVICE_FPS`.

---

## A6. ByteTrack

**Alternatives:** BoT-SORT, DeepSORT, OC-SORT.

**Why ByteTrack:** Ultralytics default, verified working, and its two-pass
association pairs unusually well with `conf=0.18` — the low threshold produces
exactly the marginal detections ByteTrack's second pass is designed to recover.

**The open question:** BoT-SORT is ~30% slower and more occlusion-robust. Since
tracking runs offline, **that 30% is free.** `compare_trackers.py` exists to
settle it and has not been run to a conclusion.

---

## A7. Persistence as a duration, not a frame count

**Alternatives:** a fixed frame count; a confidence-weighted score; no filtering.

**Why a duration:** the same rule must hold at 24 fps and at ~1.5 fps. 2.5 s is 60
frames on the clip and 3 on the Pi. A hardcoded 60 would reject every survivor on
the Pi; a hardcoded 3 would filter nothing on the clip. **Neither number is wrong;
the unit is.**

**Why 2.5 s:** `analyse_tracks.py` measured short tracks at mean confidence 0.42
against 0.52 for long ones, with only 7% at the frame edge. Low confidence,
mid-frame, gone in a frame or two is flicker. 2.5 s outlasts it and still confirms
a person crossing the frame well before they leave it.

---

## A8. Python + FastAPI backend

**Alternatives:** Flask, Django, Node/Express, Go.

**Why Python:** the whole perception stack is Python. **No serialisation boundary
between teammates' code and this service.** Robin writes Python; the backend
imports it directly.

**Why FastAPI over Flask:** type hints drive real validation, and automatic
interactive docs at `/docs` — which is free credibility during a demo.

**Why not Node:** would put a language boundary between perception and the API for
no benefit.

---

## A9. React + Vite + Tailwind + Leaflet

**Alternatives:** vanilla JS; Vue; Svelte; Next.js; Mapbox; Google Maps.

**Why React:** the largest ecosystem and the most learning material, which matters
when you are learning it under a deadline.
**Why Vite:** instant startup, hot reload, minimal config.
**Why Tailwind:** styles beside markup; no growing pile of dead CSS.
**Why Leaflet:** **no API key** — CLAUDE.md constraint 4. Mapbox and Google both
require one.
**Why not Next.js:** server-side rendering solves a problem this project does not
have.

---

## A10. Pre-computed replay, not live inference

**Alternative:** run the model live during the demo.

**Why:** live inference on stage adds a failure mode that proves nothing. The
model already ran; this *is* what it produced. It looks identical to a judge and
removes every live-inference failure mode.

**The honest framing, which is a strength rather than an excuse:**

> "The detections are real output from our trained model, run over this clip ahead
> of time. We replay them against a playback clock rather than running inference
> live, because live inference on stage adds risk and proves nothing the stored
> output doesn't already show."

---

## A11. The JSON data contract

**Alternatives:** a shared Python module; a database; direct function calls.

**Why a file format:** it decouples three people. Robin needs no Ultralytics
install. It decouples the demo from inference. And it is testable — a file either
matches the schema or it does not.

**The rule attached to it:** do not change it unilaterally. It touches all three
of you.

---

## A12. Transparent weighted priority, not a learned model

**Alternatives:** a small neural ranker; a decision tree; a hand-ordered rule
list.

**Why:** a judge will ask how the ranking works, and **"a neural network decides"
is a bad answer** for a system making rescue-order decisions. A transparent
weighted formula beats a clever opaque one.

**Why equal-ish weights (0.4 / 0.3 / 0.3):** *no term has earned the right to
dominate the other two on evidence yet.* That is an honest reason and it invites
the right follow-up question.

---

## A13. Dropping an uninformative term, not scoring it zero

**Alternatives:** score it 0.0; leave it flat at its value; skip scoring entirely.

**Why dropping:** a zero **claims a measurement nobody made.** "No hazard nearby"
and "no hazard detector" are different statements, and a rescue dashboard must not
conflate them.

Leaving a uniform term flat changes no ordering but adds a constant to everyone —
on your clip a flat **+0.4286** that lifted the entire scene into high/critical and
made a uniform crowd read as a uniformly severe one.

**Renormalising** the remaining weights redistributes rather than caps. With both
terms dropped, `score = confidence` exactly.

**Reported as `None`**, so the dashboard says "not scored" rather than printing a
confident 0.00.

---

## A14. Cluster geometry at a common reference frame

**Alternative:** each track's own frame origin (what it did before).

**Why:** the assumed flight track turns *time* separation into *ground*
separation. At 5 m/s a three-second gap manufactures fifteen metres between two
people who may have been standing together.

**What it cost before the fix:** track 1409, the highest-confidence detection in
the clip at 0.802, ranked **21st of 23**.

**The rule:** relative measurements at one reference frame; absolute measurements
at the real moving origin. The hazard term deliberately keeps the moving origin.

---

## A15. Band hysteresis at 0.03

**Alternatives:** none; a wider margin; more sampling.

**Why:** the confidence term jitters frame to frame, so a track parked near a cut
oscillates. The log showed single tracks changing band **five times in nine
seconds** — which reads as an unstable assessment when what is unstable is one
bounding box's confidence.

**Why 0.03:** three points of a 0–1 score, an eighth of the quarter-width bands it
guards. Wide enough to swallow observed jitter, narrow enough that a genuine move
still moves.

**Why it is not the same lever as sampling:** sampling sets how *often* the
question is asked; hysteresis sets how much evidence a different *answer* needs.
Sampling alone still reports a flip whenever two consecutive samples land on
opposite sides of a cut.

**Disclosed on screen**, because a survivor scored 0.76 sitting in "high" is
otherwise an unexplained contradiction of the threshold printed above it.

---

## A16. An ordinal priority ramp

**Alternative:** the original green → amber → orange → red rainbow.

**Why:** two measured failures. A rainbow has no perceptual ordering. And
red-green collapses for ~8% of men — with "serious" and "critical" measured at
**ΔE 10.6**, below the 15 floor. On a rescue dashboard that is a real defect.

**The replacement:** one hue, monotone light to dark, always paired with its text
label.

**No green anywhere.** The lowest-priority person in a disaster zone still needs
rescuing.

---

## A17. Mission parameters instead of a telemetry bar

**Alternative:** battery, GPS signal, link quality, storage, flight mode, weather.

**Why not:** *there is no aircraft.* Every one of those would be an invented number
dressed as an instrument reading — the same failure as hand-authoring detections,
and a judge only has to ask "what is this connected to?" once.

**What replaced it:** the constants the projection and ranking were computed with,
each tagged **assumed / chosen / derived / measured**.

That four-way provenance distinction is the most sophisticated idea on your
dashboard.

---

## A18. Cached OSM tiles

**Alternatives:** live OSM; Mapbox; a static georeferenced image.

**Why cached:** tiles need internet and venue wifi fails. `fetch_tiles.py` bundles
a 1 km box; the backend serves them; nothing leaves the machine on demo day.

**The trade, stated in the code:** with the backend switched off there are now no
tiles at all, where an internet connection would previously have supplied them.
That is the demo-day shape on purpose — *the venue is likelier to lose wifi than
the laptop is to lose its own uvicorn* — and the map's banner is what says so.

---

## A19. `HAZARDS = []`

**Alternative:** a plausible demo hazard to make the map interesting.

**Why empty:** hazard classification is Phase 2. **Inventing a fire is the same
failure as hand-authoring detections.**

The cost is that the priority formula runs on two terms instead of three, and on
this clip one of those is also uniform, so the score reduces to confidence. That
is a *less impressive* dashboard and a *more defensible* one, and that trade is
made deliberately throughout this project.

---

## A20. `DEVICE_FPS = None`

**Alternative:** the Mac CPU number, or a plausible estimate.

**Why null:** nobody has run the benchmark. The dashboard renders a dash and "not
yet measured."

*An invented FPS figure is the one number a judge is most likely to press on — a
Pi 4 running YOLO is exactly where a prototype is expected to be slow.*

---

## A21. Stopping training early

**Alternative:** finish all 100 epochs.

**Why:** the Colab session died. Validating what was saved showed it was good
enough — at 960 px, **P 0.864, R 0.774, mAP50 0.833, mAP50-95 0.577**. The
remaining epochs would likely have added a point or two of mAP.

**Why that was the right call:** with under two weeks left, an integration-tested
end-to-end demo is worth more than two points of mAP. **The bottleneck was never
model accuracy** — the on-device benchmark later confirmed it was not throughput
either.

**Be honest about it if asked.** "We stopped early because the numbers were good
enough and our remaining time was better spent on integration" is a strong
answer. Pretending you finished is not.

### The correction inside this decision

This entry said **epoch 44** for a fortnight, and so did five other files.
Reading the shipped checkpoint directly:

```
epoch          58        (zero-indexed → 59 completed, of a planned 100)
best_fitness   0.50397
```

Training had gone 15 epochs further than the notes recorded, and the reported
accuracy figures were from a superseded checkpoint. Nothing was fabricated — a
note was written once and never re-checked against the artefact.

**The rule this produces:** every number in the docs must be traceable to a file
you can re-read, not to a memory of having measured it. `experiments/ARES_MEASURED_NUMBERS.md`
exists to be that single source, and this is the third time in the project that
an unchecked belief was overturned by looking (see also the cluster-spread
estimate in A14 and the ONNX compile diagnosis in Part 4).

---

## A22. Borrowed footage, real detections

**Alternatives:** film your own (no drone); fully synthetic; hand-authored boxes.

**Why:** a borrowed clip with genuine model output is honest and normal for a
prototype. Invented bounding boxes are not, and one question would expose them.

---

# PART B — The mistakes

Every one of these was made, caught, and corrected. They are here because the
correction is usually more instructive than the decision.

## B1. The Colab resume that rebuilt the model with 80 classes

**What happened:** the session resumed without re-extracting the dataset.
Ultralytics fell back to `coco8.yaml` (`nc: 80`) and rebuilt the model with 80
output channels. The checkpoint was shaped for 1.

```
ValueError: loaded state dict has a different number of parameter groups
```

Compounded by a version mismatch — 8.4.120 resuming a checkpoint written by
8.4.126.

**Fix:** re-extract to the exact path, and **pin the Ultralytics version**.

**Lesson:** a training run depends on its *environment*, not just its checkpoint.

---

## B2. The dashboard showing 9 survivors on real footage

**What happened:** real detections were produced, but `config.py` still pointed at
`fixture_detections.json`. The dashboard confidently showed the fixture's 9
synthetic survivors.

**Fix:** one `sed`. **Lesson:** a fixture that looks plausible is more dangerous
than one that looks obviously fake. `make_fixture.py`'s docstring now says so in
capitals.

---

## B3. "It must be camera motion" — wrong

**The hypothesis:** the drone was moving fast enough to break IoU association.

**You corrected it:** *"no the video is smooth so sudden jump."*

**Measured:** 1.4 px/frame. Not the cause.

---

## B4. "It must be duplicate boxes" — also wrong

**The hypothesis:** NMS failing, each person getting several boxes, each spawning
a track.

**Measured:** 1.12 boxes per cluster. Essentially no duplication. Also wrong.

**The actual cause** was `imgsz`. **Lesson, and it is the best one in this
document:** two plausible hypotheses were killed by measurement before the right
one was found. That is what diagnosis looks like. It does not look like guessing
correctly first time.

---

## B5. "`max_det` is capping recall" — wrong

**The claim:** the 300 cap was already binding on your C2A test set.

**Measured:** it was never binding there.

The *decision* to set 1000 still stands — it is about the dense footage the system
is designed for — but the specific supporting claim was false and was retracted.

---

## B6. "Attention will be worse on CPU" — wrong

**The prediction:** YOLOv12's attention would be disproportionately penalised on
CPU, since attention is memory-bandwidth heavy.

**Measured:** CPU ratio 2.18× against GPU 3.14×. Attention was *relatively better*
on CPU than predicted.

---

## B7. `min_frames = 3` — a unit error, written into Robin's guide

**What happened:** a constant was written where the justification was frame-rate
dependent. Three frames is 0.125 s at 24 fps and 2 s at 1.5 fps.

**Fix:** `MIN_TRACK_SECONDS = 2.5`, with the frame count derived.

**Lesson:** when a number's justification mentions a rate, the number is not the
rule — the rate-independent quantity is.

---

## B8. The palette failed its own validator

The first palette was Tailwind defaults. Every step failed the dark-mode lightness
band, and the two most urgent bands sat at ΔE 10.6 against a 15 floor.

**Lesson:** "looks fine to me" is not a colour test. Run the validator.

---

## B9. "Pick the densest sequence" — wrong advice

**What happened:** the densest VisDrone sequence was recommended. It made
de-duplication **visible as a failure** — the gap between ID count and confirmed
count was so large it read as a broken system.

**Fix:** moderate density, where a judge can count by eye and confirm your number.

---

## B10. The cluster-spread estimate from eight visible rows

**What happened:** the survivor lat/lon spread was estimated as ~7 × 11 m from the
eight rows visible in a screenshot, and a verdict of "change nothing" was issued
on that basis.

**Measured across all 23:** 27 × 29 m. The verdict was wrong.

**Then measured properly**, at a fixed reference frame: **11.38 m**. The 27 × 29
figure was itself contaminated by the moving-origin bug.

**Lesson:** an estimate from a partial view is not a measurement, and two wrong
numbers in a row is what happens when you skip the measurement twice.

---

## B11. The moving-origin cluster bug

The real defect underneath B10. Each track was localized against its own frame's
origin, so the assumed 5 m/s track converted time separation into ground
separation. See A14.

**Lesson:** the right model for one question can be the wrong model for another.
Absolute position and relative distance are different questions.

---

## B12. `.venv-ml` in the git push

`.gitignore` listed `.venv/`, which does not match `.venv-ml/`. 182 MB pushed,
rejected by GitHub's 100 MB file limit.

**Lesson:** gitignore patterns are literal. And `git status` before every commit.

---

## B13. Guessing the event field was called `type`

A diagnostic query assumed `type`; the schema used `kind`. It returned
`{None: 65}` — a result that looked like "no events" rather than "wrong key."

**Fix:** make the next query self-describing — print the keys and the value
histogram.

**Lesson:** when a query returns something surprising, introspect rather than
guess again.

---

## B14. Sending Robin the weights but not the detections

`detections.json` is gitignored. Robin was sent the `.pt` and the `.onnx` — which
he does not need to run the dashboard — and not the one small file without which
nothing works.

**Lesson:** when handing off, check what the *clone* actually contains.

---

# PART C — Still open

| Item | Status |
|---|---|
| Pi benchmark at `imgsz=960` | Blocked on the SD card. Target both models, both runtimes, densest frame, active cooling |
| BoT-SORT comparison | `compare_trackers.py` written, not run to a conclusion |
| `MIN_TRACK_SECONDS` naming | Confirmation counts *detections*, not elapsed time. Track 1409 took 5.2 s under a constant named 2.5 |
| 3 m/s vs 5 m/s | `CLAUDE.md` implies 3, `config.py` says 5. Pick one |
| `cluster_formed` labelling | 19 events describe **one** group growing. Relabel as confirmation/growth |
| "22 others within 15 m" | `cluster_size` excludes self; the wording must say so |
| Static-mode bundle | `frontend/public/static/` exists — verify the backend-off path end to end |
| Ground-truth count | Manually count people in a few frames. Turns "23 seems right" into a measured figure |

---

## What to take from this part

- Every decision here has a **reason and a rejected alternative.** That is what
  "we designed this" means.
- The pattern running through all of them: **choose the less impressive, more
  defensible option.** Empty hazards, null FPS, a formula instead of a network,
  no telemetry bar.
- **Fourteen documented mistakes.** Three of them were confident wrong diagnoses
  killed by measurement. Say so if asked — it is evidence you did the work.

**Next:** Part 10 — the questions you will actually be asked, with answers.

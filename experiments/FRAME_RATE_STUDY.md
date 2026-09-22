# Frame-rate study — does the count survive 4.8 FPS?

**Run:** 31 August 2026 · cloud container, CPU inference
**Scripts:** `tools/frame_rate_study.py`, `frame_rate_mitigation.py`, `frame_rate_verify.py`
**Records:** `experiments/frame_rate_study.json`, `frame_rate_mitigation.json`, `frame_rate_verify.json`
**Tracker configs:** `experiments/trackers/*.yaml`

---

## 1. The question

`backend/data/detections.json` was produced by running the model over **every
frame** of a 24 FPS clip. The device does not do that. On a Dragonwing RB3
Gen 2 one inference takes 209.5 ms, so it manages **4.8 frames per second** —
a little under one frame in five.

> Does the confirmed survivor count survive the drop from the clip's frame
> rate to the one the hardware actually delivers?

Everything on the dashboard is downstream of tracking, and tracking is the part
that should care: between two processed frames the aircraft has travelled five
times as far, so boxes jump five times as far — and ByteTrack matches boxes by
how little they moved.

---

## 2. Method

The same clip, twice, changing exactly one thing:

| | frames | rate |
|---|---|---|
| full rate | every frame | 24.0 FPS |
| device rate | every 5th frame | 4.8 FPS |

Same weights (`yolov12s.pt`), conf 0.18, imgsz 960, `max_det` 1000. The
**2.5-second** persistence rule applied to both, recomputed at each rate — 60
frames at full rate, 12 at device rate. That is the payoff of having written
the rule in seconds rather than frames.

**Skipping frames is the right model of a slow device.** The device is not
handed a slower video; it is handed the same flight and manages fewer looks at
it. Dropping four frames in five is what a processor that cannot keep up does.

**Track ids are not comparable between runs.** ByteTrack numbers tracks in
order of appearance, so id 7 means different people in different runs.
Everything below matches confirmed survivors **by where and when they were**,
within 60 px on frames the two runs share.

---

## 3. The first result

| | full rate | device rate |
|---|---:|---:|
| effective FPS | 24.0 | 4.8 |
| frames processed | 312 | 63 |
| raw detections | 7,059 | 557 |
| detections per frame | 22.6 | **8.8** |
| track ids | 328 | 94 |
| persistence threshold | 60 frames | 12 frames |
| **confirmed survivors** | **21** | **10** |

> Running at the speed the hardware delivers, the system confirms **fewer than
> half** the survivors it confirms at full rate.

### The tell is detections per frame

A detector is stateless. Frame 0 is frame 0 whether or not you also looked at
frame 1 — so detections on the *same* frames cannot fall from 22.6 to 8.8
because of a detector effect.

They fall because `model.track()` does not return raw detections. It returns
what the **tracker accepted**. ByteTrack's second association stage keeps
low-confidence boxes only when they match an existing track, and our operating
point (conf 0.18, chosen for recall) leans on exactly those boxes.

One cause explains both halves: five times the frame gap means five times the
pixel motion, IoU against the previous box collapses, association fails —
tracks die *and* their low-confidence detections are discarded with them.

---

## 4. Three trackers at device rate

| rate | tracker | det/frame | ids | **confirmed** |
|---|---|---:|---:|---:|
| full | bytetrack-default | 22.6 | 328 | **21** |
| device | bytetrack-default | 8.8 | 94 | 10 |
| device | bytetrack-wide | 10.9 | 76 | **20** |
| device | botsort-gmc | 17.3 | 78 | 47 |

`bytetrack-wide` is the shipped tracker with two changes — `match_thresh`
0.8 → 0.95 (the IoU-distance gate, too tight when boxes barely overlap) and
`track_buffer` 30 → 60 frames. `botsort-gmc` adds global motion compensation,
which cancels the aircraft's own movement before boxes are compared.

**At this point the obvious conclusion is that two parameters fix it: 20
against a full-rate 21.** That conclusion is wrong, and the next section is the
reason this study has a third script.

---

## 5. Same number, different people

Matching each device-rate confirmed survivor onto the full-rate reference **by
position**, and allowing two candidates to land on the same person — because
that is what identity fragmentation looks like, and a one-to-one matcher would
hide it:

| device-rate tracker | reports | real people found | missed | duplicates | worst split |
|---|---:|---:|---:|---:|---:|
| bytetrack-default | 10 | 9 / 21 | 12 | 1 | 2 |
| **bytetrack-wide** | **20** | **13 / 21** | **8** | **5** | 2 |
| **botsort-gmc** | 47 | **20 / 21** | **1** | 17 | 5 |

> `bytetrack-wide` reports 20 against a true 21 by **missing 8 real survivors
> and double-counting 5**. The two errors partly cancel. The count looks right
> and is not.

That is the most dangerous failure mode available to this system — a wrong
number that survives inspection because it is close to the expected one. Had
this study stopped at the table in § 4, the repo would now contain a
config change described as a fix.

**BoT-SORT with GMC is the only configuration that actually sees the people**:
20 of 21 at 4.8 FPS, missing one. Its problem is the opposite and it is
visible rather than hidden — it splits identities, once into five, and reports
47.

---

## 5b. Configuring BoT-SORT — the sweep

§ 5 chose BoT-SORT because its error is recoverable and ByteTrack's is not.
Before writing a merge pass, the cheaper question: can BoT-SORT be configured to
fragment less? Two parameters govern identity creation.

`tools/frame_rate_sweep.py` · record `experiments/frame_rate_sweep.json`

| config | track_buffer | new_track_thresh | reports | **real people** | missed | dup | worst split |
|---|---:|---:|---:|---:|---:|---:|---:|
| botsort-b60-n0.25 | 60 | 0.25 | 47 | 20 | 1 | 17 | 5 |
| botsort-b150-n0.25 | 150 | 0.25 | 47 | 20 | 1 | 17 | 5 |
| botsort-b300-n0.25 | 300 | 0.25 | 47 | 20 | 1 | 17 | 5 |
| **botsort-b60-n0.5** | **60** | **0.50** | **30** | **19** | **2** | **5** | **3** |
| botsort-b150-n0.5 | 150 | 0.50 | 30 | 19 | 2 | 5 | 3 |
| botsort-b150-n0.7 | 150 | 0.70 | 5 | 4 | 17 | 0 | 1 |

Reference: 21 confirmed survivors at full rate.

### `track_buffer` does nothing — a clean negative

60, 150 and 300 give **byte-identical results**. The hypothesis behind raising it
was that fragments appear because a lost track expires before it can be
re-matched. That is wrong. A track dying of old age is not the mechanism; if it
were, a 5× longer buffer would have changed something.

What is left is that BoT-SORT **spawns a new id while the old track is still
alive** — the association fails, and a detection that cannot be matched becomes
a new identity rather than waiting. Which is why the other knob works.

### `new_track_thresh` is the whole story

| | 0.25 → 0.50 | 0.50 → 0.70 |
|---|---|---|
| duplicates | 17 → **5** (−71 %) | 5 → 0 |
| real people found | 20 → 19 (−1) | 19 → **4** (−15) |

**0.50 buys a 71 % cut in duplicates for one survivor.** 0.70 falls off a cliff —
over-suppression, 4 of 21. The knee is sharp and it sits between them.

### This does not contradict conf 0.18

They answer different questions, and the pairing is deliberate:

| | threshold | question |
|---|---|---|
| `conf` | **0.18** | is there something person-shaped here? |
| `new_track_thresh` | **0.50** | is this confident enough to be a *new person*? |

A box at 0.30 still counts as evidence and still associates with an existing
track. It just cannot **name** a new survivor. Permissive about seeing,
conservative about naming — the recall-first choice survives at the detection
stage while identity inflation is stopped at the tracking stage.

### Where this leaves the count

| | reports | real people | missed |
|---|---:|---:|---:|
| Shipped ByteTrack @ 4.8 FPS | 10 | 9 / 21 | 12 |
| **BoT-SORT b60-n0.5 @ 4.8 FPS** | **30** | **19 / 21** | **2** |
| Full-rate reference | 21 | 21 / 21 | 0 |

Finding went from **9 of 21 to 19 of 21**. The count is still inflated — 30
against a true 21 — from 5 duplicate claims and 6 tracks matching no reference
person at all.

**Adopt `botsort-b60-n0.5` for any device-rate work.** `track_buffer` stays at
60 because the higher values buy nothing and cost memory.

### Still open

- **5 duplicates** — a merge pass over co-located, time-disjoint tracks, with
  velocity extrapolation across the handoff. Must be validated in both
  directions: over-merging converts duplicates into misses.
- **6 orphans** — tracks matching no full-rate person. Either people the
  full-rate run missed, or false tracks. Unknown, and worth knowing before the
  merge, because a merge pass will move them around.

---

## 5c. One tracker, and the missing person

`tools/frame_rate_onebuild.py` · record `experiments/frame_rate_onebuild.json`

Two things § 5b left open: whether one tracker can serve both frame rates, and
whether the knee between 0.25 and 0.50 hides a better setting.

### The knee is at 0.40, and it recovers one of the two missed

| new_track_thresh | reports | **real people** | missed | dup | worst split |
|---:|---:|---:|---:|---:|---:|
| 0.30 | 43 | 20 | 1 | 14 | 5 |
| 0.35 | 43 | 20 | 1 | 14 | 5 |
| **0.40** | **38** | **20** | **1** | **9** | 4 |
| 0.45 | 34 | 19 | 2 | 7 | 3 |
| 0.50 | 30 | 19 | 2 | 5 | 3 |

**0.40 dominates 0.30 and 0.35** — the same 20 people for 9 duplicates instead
of 14. It is a strict improvement, not a trade.

Against 0.50 it *is* a trade: one more survivor found for four more duplicates.
Take it. A missed survivor is unrecoverable; a duplicate is a labelling error
over data already in hand. Same reasoning that set `conf` to 0.18.

**Revised recommendation: `botsort-b60-n0.4` — 20 of 21 found, 1 missed.**

The last one is not reachable by this knob. 0.30 and 0.35 spend five extra
duplicates and still find 20. That person is lost to the frame gap itself, and
only a higher frame rate — a faster model — would recover them.

### Fragmentation is not a frame-rate problem

The obvious reading of § 4 was that BoT-SORT fragments *because* the frame rate
is low. It does not. Run it at **full** rate:

| rate | tracker | reports | real people | missed | dup |
|---|---|---:|---:|---:|---:|
| full | bytetrack-default *(the reference)* | 21 | 21 | 0 | 0 |
| **full** | **botsort-b60-n0.5** | **53** | **20** | **1** | **14** |
| device | botsort-b60-n0.4 | 38 | 20 | 1 | 9 |

**BoT-SORT reports 53 tracks for 20 people at 24 FPS.** It fragments just as
badly with every frame available. ByteTrack, at that rate, does not fragment at
all.

So the two failures are independent:

| | cause | fixed by |
|---|---|---|
| ByteTrack loses people at 4.8 FPS | frame gap breaks IoU association | a different tracker, or a faster model |
| BoT-SORT splits identities | property of BoT-SORT on this footage, **at any rate** | a merge pass |

### What that means for having one build

There is no separate edge build, and this study is not an argument for creating
one. The tracker is a value in `backend/config.py`, not a fork.

But the choice is not free, and § 5b implied it was:

- **ByteTrack everywhere** — perfect at full rate, loses 12 of 21 at device rate.
- **BoT-SORT everywhere** — 20 of 21 at both rates, over-counts at both.

One tracker for both rates therefore means **the merge pass is load-bearing, not
optional.** Fix fragmentation once and BoT-SORT is correct at every frame rate,
which is exactly the outcome that makes a single build defensible. That is the
argument for writing it.

### Nothing here changes the demo

`detections.json` was produced by ByteTrack at 24 FPS and gives the documented
333 ids / 23 survivors. The demo replays that file. **No tracker change is
required for 10 September**, and making one would invalidate the shipped
detections. This section is about what can be claimed for on-device operation.

---

## 5d. Can a faster model rescue ByteTrack instead?

`tools/frame_rate_threshold.py` · record `experiments/frame_rate_threshold.json`

An attractive alternative to BoT-SORT plus a merge pass: ByteTrack fails because
of the frame gap, so close the gap. Run a lighter detector, get more FPS, and
the cheap tracker works unmodified — no GMC, no merge.

The plan needs a number before it needs a model. **How many FPS does ByteTrack
require?**

| FPS | gap | budget / frame | reports | **real people** | missed | dup |
|---:|---:|---:|---:|---:|---:|---:|
| 24.0 | 1 | 41.7 ms | 21 | **21 / 21** | 0 | 0 |
| 12.0 | 2 | 83.3 ms | 18 | **15 / 21** | 6 | 3 |
| 8.0 | 3 | 125.0 ms | 17 | 13 / 21 | 8 | 3 |
| 6.0 | 4 | 166.7 ms | 11 | 11 / 21 | 10 | 0 |
| 4.8 | 5 | 208.3 ms | 10 | 9 / 21 | 12 | 1 |

### There is no plateau to aim at

**Halving the frame rate — one skipped frame — already costs 6 of 21 people.**
The degradation is not a cliff that appears at low rates; it starts at the very
first frame dropped and continues steadily. ByteTrack needs essentially every
frame.

That sets the budget at **41.7 ms per inference**. YOLOv12s at 960 on the RB3
Gen 2 measures **209.5 ms**. Required speed-up: **5.0×**.

### The arithmetic does not reach

YOLOv8n is 8.1 GFLOPs against YOLOv12s' 23.2 — **2.9× fewer**. Even granting a
perfect FLOP-to-latency translation, which no NPU offers, that lands at ~72 ms,
or ~13.9 FPS.

At 12 FPS ByteTrack finds **15 of 21**. BoT-SORT at 4.8 FPS finds **20 of 21**.

> A lighter model with ByteTrack, at the best speed-up the architecture could
> plausibly give, is **worse** than the heavier model with BoT-SORT at the frame
> rate we already measured.

And that is before YOLOv8n's lower per-frame recall (0.728 against 0.774) is
counted, which pushes it further down.

**Do not confuse this with the 640-vs-960 argument.** That one turns on
resolution: a person too small to resolve at 640 stays too small on every
subsequent frame, so the failures are correlated and extra looks do not help. A
lighter *architecture* at the same 960 is a different trade — the person is
still resolved — and its failures are less perfectly correlated. The conclusion
happens to point the same way; the reasoning does not transfer.

### The compute saving is real and negligible

Measured on identical device-rate runs, CPU, 63 frames:

| tracker | ms / frame (whole pipeline) |
|---|---:|
| bytetrack-default | 488.9 |
| bytetrack-wide | 490.5 |
| **botsort-gmc** | **501.6** |

GMC costs **12.7 ms per frame, about 2.6 %** of the frame budget. It buys
eleven survivors. The tracker is noise next to the detector; optimising it is
optimising the wrong term.

*(CPU numbers, from this container. Indicative of the ratio, not of on-device
latency.)*

### Conclusion

The instinct is directionally right — more FPS genuinely does fix ByteTrack —
but quantitatively out of reach. The curve is too steep and the gap is 5×.

**BoT-SORT + a merge pass remains the path.** A faster model is still worth
having for other reasons, and it would recover the one survivor
`botsort-b60-n0.4` still misses. It is not a route around the merge.

---

## 6. What this means

The two problems are **separable**, and only one of them is solved:

| | at 4.8 FPS |
|---|---|
| **Finding** survivors | Solved — BoT-SORT + GMC holds 20 of 21 |
| **Counting** them once | **Not solved** — every config either misses people or splits them |

`backend/tracks.py` already names this exact limitation:

> *"an ID switch, where one person picks up a second ID after an occlusion.
> Both halves persist past the threshold, so both are confirmed and the
> survivor count is one too many. That is a tracker problem."*

It is now measured rather than anticipated, and it is worse at device rate than
at full rate.

### What may and may not be claimed

**May:**

> At the device's measured 4.8 FPS, BoT-SORT with global motion compensation
> keeps 20 of 21 survivors that full-rate tracking finds, but fragments
> identities badly enough that the de-duplicated count is not yet reliable at
> that rate. Measured, 31 August.

**May not:**

> The system produces the same survivor count on device.

### The demo is not affected

The demo replays a pre-computed `detections.json` produced at the clip's full
24 FPS, exactly as `CONVENTIONS.md` specifies. Nothing on stage depends on
device-rate tracking. What this study constrains is the **claim**, not the
demonstration.

---

## 7. The obvious next step, not yet taken

BoT-SORT's fragments are co-located in space and disjoint in time — one person,
several ids, handed off in sequence. A merge pass (union tracks whose
trajectories fall within N px and do not overlap in time) is the standard
remedy and would plausibly bring 47 toward 21.

It is not in this study because it would need validating the same way — against
the full-rate reference, by position — and an unvalidated merge would repeat
the § 5 mistake with extra steps.

---

## 8. Caveats

1. **CPU inference, not the Qualcomm board.** This measures the *effect of the
   frame rate* on tracking, not on-device latency. Latency is measured
   separately in `QUALCOMM_BENCHMARK.md`.
2. **ultralytics 8.4.135**, against 8.4.129 for the shipped `detections.json`.
   The full-rate rerun gives 328 ids / 21 confirmed where the shipped file
   documents 333 / 23 — close enough to validate the harness, not identical.
   Quote the shipped file's numbers for the demo and these for this study.
3. `track_buffer` is counted in **frames**, so at device rate a lost track is
   retained 6.2 s rather than 1.25 s. That is not a thumb on the scale — the
   board would run the same default at the same rate.
4. One clip, one scene type. Dense urban VisDrone footage.
5. Matching tolerance is 60 px at 1280×720. Not tuned; a sweep would firm up
   the duplicate counts.

# Part 10 — Judge Q&A

The questions you will actually be asked, with answers grounded in your real
numbers. Read this the night before.

**The rule underneath all of it:** if you do not know, say so and say what you
would do to find out. A confident wrong answer is the only kind that loses you
the room.

---

## The opening — say this before they ask

Sixty seconds, delivered up front. It pre-empts the three questions that would
otherwise be asked with suspicion.

> "ARES detects survivors from drone imagery, tracks them so we don't
> double-count, puts them on a map, and ranks them for rescue order.
>
> Three things you should know before I show it.
>
> **We don't own a drone**, so the footage is a public UAV dataset. The
> detections are our own trained model's real output over that footage — the
> flight is borrowed, the perception is ours.
>
> **The demo replays a pre-computed file** rather than running inference live.
> The model already ran; this is what it produced. Live inference on stage adds
> risk and proves nothing.
>
> **Some of what we describe isn't built.** Autonomous navigation and GPS-denied
> SLAM are architecture, not code, and the dashboard doesn't pretend otherwise."

**Why open this way:** every one of those, discovered by a judge, is a
credibility hit. Volunteered, each is evidence of judgment.

---

# 1. The model

### "What model is this and why?"

> YOLOv12s. Ultralytics-native, so tracking and ONNX export work without
> integration work. The `s` size is 9.3 million parameters — `n` loses too much
> accuracy on small aerial targets where every pixel counts, and `m` and up are
> too slow for a Raspberry Pi. We compared it against YOLOv8 directly and the
> comparison is written up in the repo.

### "What accuracy do you get?"

> Precision 0.864, recall 0.774, mAP50 0.833, mAP50-95 0.577 — at 960 pixels,
> on the combined C2A + VisDrone validation split, 2,591 images and 86,092
> instances.
>
> For context, YOLO12s scores 48.0 mAP50-95 on COCO — and COCO is mostly large,
> centred, well-lit objects. We get **57.7 on small aerial humans**, which is a
> harder problem, from a 9.2-million-parameter model.
>
> At the threshold we actually ship, 0.18, recall is **0.824**.

### "Why 960 pixels and not 640?"

> We measured both, same checkpoint. 640 gives us mAP50-95 0.511 and recall
> 0.727; 960 gives 0.577 and 0.774. Resolution buys us **4.7 points of recall**
> on aerial targets that are only a few pixels tall.
>
> It costs about 7.8× the compute duty cycle on our target board. We think
> that's the right trade for search and rescue, and we can show you the number
> rather than assert it.

### "How many epochs did you train?"

**Answer honestly. This is a test of whether you'll spin.**

> The shipped checkpoint records epoch 58 of a planned 100 — 59 epochs. The
> Colab session died before it finished. We validated what we had, it was good
> enough, and with the time remaining an integration-tested end-to-end system was
> worth more than the point or two of mAP the last epochs would have added.
> Model accuracy was never our bottleneck.
>
> Worth adding: our own notes said epoch 44 for a while. We caught it by reading
> the checkpoint instead of the notes, and corrected it.

### "Your confidence threshold is 0.18. Isn't the default 0.5?"

**This is your best question. Take it slowly.**

> It is, and we changed it deliberately. In search and rescue the costs are
> wildly asymmetric — a false alarm costs a rescuer thirty seconds of walking,
> and a missed survivor cannot be recovered.
>
> We read the threshold off the precision-recall curve from our validation run.
> At the F1-optimal 0.37, recall is 0.775. At our 0.18 it's 0.824 — about three
> extra false alarms for every additional person found. That's forty-nine more people
> found per thousand present.
>
> The price is more false positives, and we handle those downstream with a
> persistence filter rather than by raising the threshold and losing people.

### "What would you improve about the model?"

> In order: finish training; train at 960 to match our inference size; and tiled
> inference — SAHI — which slices a large frame into overlapping tiles. That's
> the standard technique for small objects in large images and is probably the
> single biggest accuracy gain available to us. It multiplies inference cost, so
> it needs the on-device benchmark first.

---

# 2. Data and honesty

### "Is this your model's output?"

> Yes. Every box on screen came from our trained weights run over this clip. The
> clip is borrowed — a public UAV dataset, because we don't have a drone — but
> nothing in the detections is authored.

### "Why not fly your own drone?"

> No aircraft and no budget for one. A borrowed clip with real detections tests
> the same perception pipeline; what it doesn't test is flight, and we don't
> claim it does. The altitude, field of view and flight track are assumed
> constants, and the dashboard tags them as assumed rather than burying them.

### "How do I know you didn't just draw those boxes?"

> Scrub the video. The boxes flicker in and out on marginal detections and the
> confidence values vary continuously — that's what a detector at a 0.18
> threshold looks like. Hand-drawn boxes would be steadier and cleaner than
> this. And the repo has the script that produced the file, so you can re-run it.

### "Why is the hazard list empty?"

> Because the hazard classifier is Phase 2 and we haven't trained it yet.
>
> We could have put a fire on the map to make it look busier. Then the priority
> ranking would be responding to something we invented. The scoring code treats a
> missing hazard layer as *not measured* and drops the term entirely, rather than
> scoring it zero — because "no hazard nearby" and "no hazard detector" are
> different claims.

---

# 3. Counting and tracking

### "Why are there three different numbers in the header?"

> Because they're three different questions, and the gaps between them are the
> interesting part.
>
> **7,081** raw detections — every box the model drew across the clip.
> **333** unique track IDs — every identity the tracker issued.
> **23** confirmed survivors — the tracks that persisted for two and a half
> seconds.
>
> Showing only 333 would overstate the survivors by an order of magnitude.
> Showing only 23 would hide what the filter is doing and give you no way to
> check it.

### "333 to 23 is a huge drop. Isn't the tracker broken?"

> No — that gap is the price of the 0.18 threshold, and it's the other half of
> that decision.
>
> At a recall-first threshold the detector reports anything person-shaped: a
> shadow, a bag, a patch of rubble. The tracker gives each one an ID. We measured
> those short tracks — mean confidence 0.42 against 0.52 for long ones, and only
> 7% starting or ending at the frame edge. Low confidence, mid-frame, gone in a
> frame or two is flicker, not a person walking out of shot.
>
> So persistence is the right filter. Dropping the confidence threshold instead
> would have cost us real survivors.

### "Why two and a half seconds?"

> It's long enough to outlast the flicker we measured and short enough that
> someone crossing the frame is confirmed well before they leave it.
>
> And it's expressed as a **duration**, not a frame count, deliberately. Two and
> a half seconds is 60 frames on this 24 fps clip and 3 frames on a Raspberry Pi
> at 1.5 fps. A hardcoded 60 would reject every survivor on the Pi; a hardcoded 3
> would filter nothing here. The rule is the duration.

### "Does the filter fix everything?"

**Do not oversell this.**

> No. It removes flicker. It does not fix ID switches — where one person picks up
> a second ID after walking behind something. Both halves persist, so both get
> confirmed and the count is one too many.
>
> That needs a better tracker, not a longer threshold. BoT-SORT would help; it's
> about 30% slower, which costs us nothing because tracking runs offline. We have
> the comparison script written and haven't run it to a conclusion yet.

### "You had a bug here, didn't you?"

**If they've read the repo, own it — the diagnosis is the strong part.**

> A bad one. We were getting 350 IDs for about 23 people. We thought it was
> camera motion — measured it, 1.4 pixels per frame, not the cause. We thought it
> was duplicate boxes from failing NMS — measured it, 1.12 boxes per cluster, not
> that either.
>
> It was input resolution. We were detecting at 640 on a 1280-wide clip, so every
> frame was halved and a 24-pixel person reached the network at 12 pixels — below
> what the model resolves reliably. Detections flickered, and no tracker can hold
> an identity across boxes that keep vanishing.
>
> We swept 640, 960 and 1280 and took 960 on the measurements.

---

# 4. Localization

### "How do you get GPS from a camera?"

> Nadir projection with a known altitude. If the camera points straight down from
> 20 metres with a 60-degree field of view, it sees `2 × 20 × tan(30°)` = about 23
> metres of ground across 1280 pixels. That's 1.8 centimetres per pixel.
>
> A pixel offset from the centre of the frame is a ground offset from the drone's
> position, and metres convert to degrees at 111,320 per degree of latitude, or
> that times the cosine of the latitude for longitude.

### "How accurate is it?"

**Never overclaim this one.**

> Good enough to put a pin on the right building. Not survey grade.
>
> The error budget is dominated by the assumed altitude and attitude — a 10%
> altitude error is a 10% scale error, terrain relief adds more, and a five-degree
> tilt off nadir shifts the whole footprint by nearly two metres. Realistically
> we're at one to two metres of relative uncertainty.
>
> The flat-earth approximation contributes about a millimetre, so it isn't the
> limiting factor. Replacing it with a proper geodesic would be theatre.

### "What breaks at higher altitude?"

> Detection, not the maths. Above roughly 40 metres a 1.7-metre person spans
> fewer than 24 pixels at 640-pixel input, and the model stops resolving them
> reliably. That's our measured operating ceiling and we state it rather than
> claiming the system works at any height.

### "You assume the drone flies in a straight line?"

> Yes, and it's disclosed on the dashboard as an assumed parameter.
>
> There's no telemetry in the prototype, so we assume a constant-velocity track.
> Without it, every survivor in the clip would pile into one 23-metre square
> regardless of how long the drone flew, which isn't what a search flight looks
> like. With real telemetry, `origin_for_frame` is the only function that has to
> change.

---

# 5. Priority scoring

### "How does the ranking work?"

> A weighted average of three normalised terms: detection confidence at 0.4, how
> many other survivors are within 15 metres at 0.3, and proximity to the nearest
> hazard at 0.3.
>
> It's a transparent formula rather than a learned model on purpose. You're
> asking how rescue order is decided, and "a neural network decides" is a bad
> answer to that question.

### "Why those weights?"

> They're deliberately equal-ish, because no term has earned the right to
> dominate the other two on evidence yet. When we have hazard data and real
> outcomes to validate against, that's a question we can answer with numbers
> instead of judgment.

### "Why is 0.75 the critical threshold?"

> They're the quarters of the range. The score is 0 to 1, so the cuts are 0.25,
> 0.50, 0.75.
>
> We deliberately didn't fit them to this clip's score distribution — thresholds
> tuned to make a demo look colourful are the same failure as inventing data.

### "So on this clip the score is just detection confidence?"

**They may well spot this. Have it ready.**

> On this clip, yes, and the dashboard says so in those words.
>
> Hazards aren't measured — that term is dropped. And all 23 survivors are inside
> an 11-metre patch, so every one of them has the same 22 neighbours; a term with
> the same value in every row can't rank those rows, so it's dropped too and the
> remaining weight renormalises.
>
> What's left is confidence. And ordering by confidence isn't meaningless here:
> at a 0.18 threshold a low-confidence box is about as likely to be a shadow as a
> person, so the queue is ordered by how likely each dispatch is to find someone.
>
> We verified the cluster term works when the data allows it — a synthetic scene
> with an isolated survivor and a pair 200 metres away scores 0.0, 0.25, 0.25.

### "Why is a survivor scored 0.76 in the 'high' band when the cut is 0.75?"

> Hysteresis, and it's stated on that panel.
>
> A band is a state that gets re-read, and the confidence term jitters frame to
> frame — so a track parked near a cut oscillates across it. Our event log showed
> single tracks changing band five times in nine seconds, which reads as an
> unstable assessment when what's unstable is one bounding box's confidence.
>
> There's a three-point deadband around each cut: climbing to critical needs
> 0.78, falling back to high needs below 0.72. It delays a band change; it never
> hides one.

---

# 6. On-device

### "Have you actually run this on hardware?"

**If the benchmark isn't done, say so plainly.**

> Not yet — we're waiting on an SD card. The dashboard shows a dash and "not yet
> measured" rather than a number, because an invented FPS figure is exactly the
> kind of claim one follow-up destroys.
>
> We've exported to ONNX and verified that YOLOv12's attention blocks export
> cleanly, which was the real technical risk. The benchmark is a measurement,
> not an unknown.

*(If it is done, give the real number and go straight to the next answer.)*

### "What frame rate do you actually get on device?"

**This is the answer that wins the hardware round. It is a measurement.**

> We benchmarked on Qualcomm AI Hub, on real hosted silicon. At 960 pixels,
> INT8: **4.8 FPS on a Dragonwing RB3 Gen 2, 16.1 FPS on an IQ-9075.** Peak
> memory under 10 MB. And **489 of 489 layers — 100 % — execute on the Hexagon
> NPU**, with nothing falling back to CPU.
>
> The 100 % is the part we'd point at. An attention-centric YOLOv12 maps
> completely onto your accelerator.

### "Is 4.8 FPS enough?"

> More than enough, and we can show why. At 20 metres altitude the camera sees
> 23 metres of ground, so at 5 m/s the aircraft takes 4.6 seconds to cross its
> own footprint. At 4.8 FPS that's **about 22 looks at every patch of ground.**
>
> Compute stopped being our binding constraint. The remaining hard problem isn't
> throughput, it's whether the detector finds a half-buried person at all — a
> recall problem, and that's where we spent the effort.
>
> **A search UAV doesn't need 30 FPS. It needs to not miss the ground.**

### "Then why not run at 640 and go even faster?"

> We measured that too — 35.2 FPS on the RB3, which is about 163 looks per
> patch. But detection failures across consecutive frames are **correlated**, not
> independent: a person too small to resolve at 640 is still too small in the
> next frame. You'd be spending compute to re-fail the same detection 152 more
> times, and giving up 4.7 points of recall on every one of them.
>
> Past the point where coverage saturates, resolution is the better purchase.

### "How would you make it faster?"

> INT8 quantisation first — roughly 4× smaller and substantially faster on CPU
> for a small accuracy cost, and it's the standard next step for edge deployment.
> Then NCNN instead of ONNX Runtime, which is hand-optimised for ARM. Beyond
> that, an accelerator — a Coral TPU or a Hailo HAT — though that changes the
> claim from "commodity hardware" to "hardware with an accelerator", which is
> weaker and I'd want to be clear about it.

---

# 7. Architecture and software

### "Where does the search algorithm actually run?"

> On the aircraft. Everything that makes a decision runs onboard — detection,
> tracking, localization, priority, and the planner that picks where to fly
> next. The ground station receives survivor records and draws the map. It does
> not issue commands.

**Follow-up you should invite:** *"Why not run the planner on the ground, where
there's more compute?"*

> Because the planner commits to a new target every twenty seconds. Over a
> twenty-minute sortie that's sixty decisions, and on the ground every one of
> them is a radio round trip — sixty single points of failure, and the moment
> the link drops the aircraft has no next target. We put the loop where it can
> close without a radio.

**The sentence to have ready:**

> *"The link carries information out, not commands in. Losing it costs the
> operator live awareness. It does not stop the search."*

---

### "Can one drone really carry all of that?"

Do not estimate this out loud. The numbers exist:

| Stage | Time | Runs |
|---|---:|---|
| **Detection @960 INT8** | **209.5 ms** | every frame *(measured, RB3 Gen 2)* |
| Localization, 23 survivors | 0.25 ms | every frame |
| Priority scoring, O(n²) | 1.57 ms | every frame |
| **Planner — 400 cells + argmax** | **0.28 ms** | **once per 20 s** |

> Everything after detection costs under one percent of the frame budget —
> 0.87 %. The planner runs once every twenty seconds and takes 0.28
> milliseconds, a duty cycle of 0.0014 %. Detection is the entire cost. The
> intelligence on top of it is effectively free.

Two things make that answer safe to give:

- **It is two computers, not one.** A Pixhawk-class flight controller runs
  ArduPilot and handles stabilisation and failsafe; the Qualcomm companion
  computer runs perception and planning and hands targets down over MAVLink. If
  the companion board dies, the aircraft still flies and still comes home.
- **The timings are from our own code**, run over the demo clip's 7,081
  detections and the 20×20 planner grid, then scaled 8× as a pessimistic ARM
  allowance — not from a datasheet.

**If they push on what *is* hard, say it plainly:** running two detectors for
RGB + thermal fusion measured 2.4 FPS; sustained thermal and power draw are
**not measured**; and the integration itself is not built — the loop has only
ever closed in simulation.

---

### "YOLOv8s scores higher than YOLOv12s. Why are you shipping v12s?"

This is a strong question and the honest answer is better than a dodge:

> Because accuracy was only half the question. We ran the controlled comparison
> — same data, same split, same resolution, epoch-matched — and YOLOv8s did
> win: recall 0.8264 against 0.8234, and 2,273 fewer false positives. But v8s
> is the heavier network, 11.1 million parameters against 9.2, and our binding
> constraint is a 209.5 millisecond frame on the device, not mAP. The swap is
> gated on a latency benchmark, and we fixed the rule before we had the number:
> faster than 209.5 milliseconds, we swap; slower, we keep v12s.

**Why this lands well:** it shows a pre-registered decision rule. Volunteering
that your current model is not the most accurate one you trained is the kind of
answer judges remember.

---

### "Why is offline resilience a feature?"

> It isn't one — it's a consequence, and that's a stronger position.
>
> Because inference happens on the aircraft, losing the network costs us the
> video feed and nothing else. The survivor count, the map positions and the
> ranking are already computed. We send a few kilobytes of structured data
> instead of a video stream. We didn't build offline resilience; we chose an
> architecture that has it.

### "Show me how the pieces fit together."

> Detection and tracking write a JSON file — one record per person per frame,
> with a persistent track ID. That file is the contract between three people's
> code, and it means my teammate doesn't need PyTorch installed to develop
> localization against real data.
>
> The backend reads that file, converts pixels to GPS, scores priority, and
> serves it over a small REST API. The dashboard renders it. Every derived value
> — position, score, band — is computed server-side, so the JSON contract carries
> what the model *saw* and never what we concluded.

### "Why FastAPI?"

> The whole perception stack is Python, so there's no serialisation boundary
> between my teammates' code and this service. And the type annotations do real
> validation rather than documentation — a malformed detection record is rejected
> at the boundary rather than surfacing as a survivor at latitude 4,000.

### "What happens if the backend crashes during your demo?"

> The dashboard still renders. The clip is served from the frontend's own
> directory, and there's a static bundle of the survivor, event and config data
> it falls back to. The header shows an offline badge, so it says out loud that
> the figures are local rather than live.
>
> What we'd lose is the cached map tiles, since the backend serves those — the
> pins stay, the base map goes, and the map panel says so.

### "Why does the dashboard show no battery or GPS signal?"

**A great question to get. Answer it with enthusiasm.**

> Because there's no aircraft. Any battery percentage on that screen would be a
> number I typed, presented as an instrument reading.
>
> What we show instead are the constants the projection and ranking were computed
> with, and each row is tagged with where the number came from: **assumed** for
> altitude and the flight track, **chosen** for the input size and confidence
> threshold, **derived** for anything computed from those, and **measured** for
> actual observations. Exactly one row can ever be tagged measured, and it hasn't
> earned it yet.

---

# 8. Scope

### "Which parts are actually built?"

> Built: on-device inference, priority scoring, the dashboard, geo-tagged
> mapping, and offline resilience.
>
> Partial: RGB-thermal fusion, which we demonstrate on public thermal datasets
> rather than hardware. And hazard classification — three of the seven classes,
> in Phase 2.
>
> Described only: autonomous navigation and GPS-denied SLAM. That's an
> architecture write-up. We deliberately didn't mock it, because a SLAM panel
> showing a map that isn't real is worse than not having one.

### "Why not build the autonomous navigation?"

> It's the hardest item on the list and we have three people and twelve days. We
> chose to make a smaller set of things genuinely work rather than make everything
> appear to. We'd rather you ask us hard questions about what's on the screen than
> discover that half of it is a mock-up.

### "What's your biggest weakness?"

**Never say "we don't have any."**

> ID switches. If someone walks behind a structure and comes back out, they can
> pick up a second identity, and both halves clear our persistence threshold, so
> the count is one too many. We know it happens, we know persistence doesn't fix
> it, and the dashboard states the limitation rather than implying it's solved.
>
> The fix is a re-identification-capable tracker, which is more compute. That's a
> measured trade we haven't made yet.

---

# 9. Hostile questions

### "This is just YOLO with a dashboard, isn't it?"

> The detector is off the shelf and we'd be lying if we said otherwise. What's
> ours is everything between a detector and a decision.
>
> A raw detector gives you 7,081 boxes. Getting from there to "twenty-three
> people, here they are on a map, go to this one first" is de-duplication,
> evidence thresholding, coordinate projection and a ranking you can explain.
> Every one of those has a failure mode we hit and fixed.
>
> And I'd argue using an off-the-shelf detector is the right call — training our
> own architecture would be worse and would have consumed the twelve days.

### "Your priority score is just confidence. That's not priority."

> On this clip, correct, and the dashboard says so rather than hiding it.
>
> The formula has three terms. One isn't measured — no hazard classifier yet. One
> can't discriminate on this footage because all 23 people are in one 11-metre
> group. We drop terms that can't rank rather than scoring them zero, so what
> remains is confidence.
>
> That's a limitation of this clip, not of the design, and we verified the
> mechanism works when the data supports it. We could have manufactured a hazard
> to make it look richer. That seemed worse.

### "How do we know any of these numbers are real?"

> Everything on screen comes from one file and one endpoint, and both are in the
> repo. The API's interactive docs are at `/docs` — you can call any endpoint
> yourself right now. The script that produced the detections is in `tools/`, and
> the constants are in one config file with the reasoning written above each one.
>
> The dashboard's own design rule is that a number appears once, not twice — the
> header's survivor count and the table's row count are the same array, not two
> calculations that agree.

### "What if I told you your survivor count is wrong?"

> I'd want to know which direction. If it's over, the likely cause is ID
> switches, which we know about. If it's under, that's more serious and I'd want
> to look at the clip.
>
> Honestly, the thing we're missing is a ground-truth count — manually counting
> the people in a few frames and comparing. That would turn "23 looks right" into
> a measured accuracy figure, and it's the first thing I'd add.

---

# 10. Things to never say

| Don't say | Say instead |
|---|---|
| "The AI figures it out" | Name the actual mechanism |
| "It's about 95% accurate" | Quote precision, recall and mAP separately |
| "It works in real time" | "It runs at N FPS on a Pi 4, and here's why that's enough" |
| "We don't have any weaknesses" | ID switches, no ground-truth count, INT8 accuracy unmeasured, sustained power/thermal unmeasured |
| "That's just a placeholder" | If it's on screen, defend it or remove it before the demo |
| "That part was already written" | Say who owns the module and what it does. Every file here has an owner |

---

## The last five minutes before you present

- [ ] Backend running, dashboard loaded, clip playing
- [ ] `/docs` open in a second tab
- [ ] `backend/config.py` open in the editor
- [ ] Wifi off, and the dashboard checked — tiles cached, static bundle working
- [ ] The three numbers memorised: **7,081 / 333 / 23**
- [ ] The recall numbers memorised: **0.824 at 0.18 vs 0.775 at the F1-optimal 0.37 — ~3 false alarms per extra survivor**
- [ ] The footprint argument ready: **23 m of ground, ~5 s to cross, 5+ looks**
- [ ] One sentence ready for each of: borrowed footage, pre-computed replay, SLAM
      not built

**Next:** Part 11 — what to learn next and where.

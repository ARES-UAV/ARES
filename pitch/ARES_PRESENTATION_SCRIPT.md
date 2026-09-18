# ARES — how to present the deck

**Built for 6 minutes + Q&A.** A 3-minute compression is at § 6.
Every number here is measured; nothing is estimated.

---

## 1. The one sentence everything hangs on

> **Search is a decision problem, not a coverage problem.**

Say this early and let the rest of the talk prove it. If a judge remembers one
idea from your six minutes, make it this one — because it is the thing nobody
else in the room will be saying.

Everything in ARES ladders to it:

| | |
|---|---|
| Detection | you can **see** |
| Tracking | you can **count** |
| Localization | you can **place** |
| Priority scoring | you can **rank** |
| Adaptive search | you can **decide** ← the actual contribution |
| Honest scope table | you can be **trusted** |

---

## 2. The story arc, and why this order

Most teams present features in the order they built them. That is the order
that makes sense to *you*, not to a listener. Use this instead:

```
   a question nobody can answer          →  hooks them
   the answer everyone uses today        →  sets the baseline
   the arithmetic showing why it fails   →  the surprise
   what we do instead                    →  the idea
   the obvious objection, raised by YOU  →  earns trust
   the measurement that answers it       →  the proof
   what we did not build                 →  seals the trust
```

**The single most powerful move in this deck is raising the objection
yourself.** Judges spend all day listening to teams hide weaknesses. A team
that says *"here is the case where our method has no advantage, and here is
what it does"* becomes the credible one in the room instantly.

---

## 3. Slide-by-slide script

Words in **bold** are the lines to say close to verbatim. Everything else is
yours to phrase naturally.

---

### Slide 1 · Title — 20 seconds

Do not read the slide. Ask the room a question and actually pause.

> **"You have a drone with twenty minutes of battery, and half a square
> kilometre of disaster zone. Where do you fly first?"**

*(pause — two full seconds, let them think)*

> **"Today, the honest answer is: everywhere, equally. And that is the problem
> we worked on."**

Then: team name, problem statement, one line on what ARES is. Ten seconds.

**Do not** open with *"ARES is a UAV-based disaster search-and-rescue system
that…"* — that is a definition, and definitions do not make anyone lean in.

---

### Slide 2 · The idea — 90 seconds

**Beat 1 — the baseline (15 s).** Point at "THE PROBLEM".

> **"A search drone flies a grid. Back and forth, every square metre gets the
> same attention — the collapsed building and the empty field, equally."**

**Beat 2 — the arithmetic reveal (25 s). This is your best moment. Slow down.**

> **"We simulated a hundred missions. The grid drone covers the whole area —
> and it still plateaus at seventeen survivors out of twenty. Forever."**
>
> *(pause)*
>
> **"Not because it ran out of battery. Because our detector finds
> eighty-two in a hundred, and twenty times zero-point-eight-two-four is
> sixteen and a half. Flying the same ground again doesn't fix that. The
> arithmetic was always against it."**

Why this works: you are not claiming the grid is bad, you are **showing why**.
Understanding is far more persuasive than assertion, and this number is the one
they will repeat to each other afterwards.

**Beat 3 — the idea, with the analogy (25 s).** Point at the loop diagram.

> **"So ARES doesn't cover — it decides. It builds a live probability map while
> it flies and always goes to the best ground it hasn't searched yet."**
>
> **"It's how you look for your keys. You don't scan your house in a grid. You
> check the table, the jacket, the car. And if you still haven't found them,
> you eventually go back to the places you skipped."**
>
> **"That second half is the important half, and it's in the algorithm — a cell
> we skip gets staler and staler until it outranks a mildly interesting one."**

The keys analogy makes a Bayesian belief map with a staleness term legible to a
non-technical judge in nine seconds. Use it.

**Beat 4 — the three numbers (25 s).** Point at the stat cards.

> **"Twenty of twenty found, against eleven for the grid. Three point two times
> faster to reach half of them. And all of it runs on the drone — a hundred
> percent of the model on the onboard AI chip."**
>
> **"In simulation, for the first two. I'll come back to that."**

**Never say "three times faster" without "in simulation".** Flagging it
yourself, once, early, costs you four words and buys you the room's trust for
the rest of the talk.

---

### Slide 3 · Technical approach — 100 seconds

**Beat 1 — the loop (30 s).** Trace the top row of the diagram left to right
with your finger or the pointer. Do not read the boxes.

> **"Two cameras feed a fusion step. Tracking makes sure each person is counted
> once. Everything above this dark bar happens on the drone."**
>
> **"This bar is the data contract — the one format our three sub-teams agreed
> on before anyone wrote code. Below it is the ground station, which also
> works with no internet."**
>
> **"And this orange arrow is the whole project: the planner sends the next
> search target back to the flight controller. The drone changes its own
> route."**

**Beat 2 — the counting problem (20 s).** This is a detail most teams never
even notice, which is exactly why mentioning it lands.

> **"One thing that surprises people: a detector can't count. Over our demo
> clip it fires seven thousand and eighty-one times. That is not seven
> thousand people. Tracking collapses it to three hundred and thirty-three
> candidates, and a persistence rule confirms twenty-three real survivors."**
>
> **"If your dashboard reports raw detections, it is lying to the rescue team."**

**Beat 3 — the dashboard (15 s).** Point at the screenshot.

> **"This is running, not a mockup. Live map, rescue queue ordered by priority,
> and an event log where every line comes from a detection — nothing is
> hand-written."**

**Beat 4 — real silicon (35 s).** This is the Hardware Edition. Spend the time.

> **"We benchmarked on real Qualcomm silicon through AI Hub — physical hosted
> devices, not emulators. Four hundred and eighty-nine of four hundred and
> eighty-nine layers run on the Hexagon NPU. Nothing falls back to the CPU."**
>
> **"That's two hundred and nine milliseconds a frame — under five frames a
> second. Which sounds slow."**
>
> *(pause — let the objection form in their heads)*
>
> **"At twenty metres the camera sees twenty-three metres of ground, and the
> drone crosses that in under five seconds. Every patch of ground gets about
> twenty-two looks. Compute isn't our bottleneck — per-look accuracy is."**

Letting the judge think *"4.8 FPS is bad"* and then answering it three seconds
later is far stronger than pre-empting it. They get to be right, then get to be
corrected by evidence. That sequence is memorable.

---

### Slide 4 · Feasibility — 70 seconds

**Beat 1 — the left column (20 s).** Do not read all six rows. Pick two.

> **"Six things are built and measured. The two that matter most: our detector
> finds eighty-two people in a hundred across eighty-six thousand labelled
> examples, and the whole thing runs on a drone-class board."**

**Beat 2 — the scope table (35 s). This is where you win or lose credibility.**

> **"We're precise about what is built and what isn't."**
>
> **"Built and measured: detection, tracking, localization, priority, the
> dashboard, the on-device benchmark."**
>
> **"Partial, and we say partial: fusion is measured on public paired data, not
> on a drone we own. Hazard classification is three classes, not seven —
> because three are the ones we have metrics for."**
>
> **"Simulated, not flown: the adaptive planner. There is no aircraft. We are
> not going to stand here and imply there is."**
>
> *(pause)*
>
> **"We'd rather show you a smaller system that's true than a bigger one that
> isn't."**

That last line is the emotional centre of the whole pitch. Say it slowly, look
at the judges, and stop.

**Beat 3 — in progress (15 s).** Point at the amber box.

> **"And these are the numbers still being measured. They're on the slide
> because they aren't finished yet, not because we forgot them."**

---

### Slide 5 · Impact — 60 seconds

**Beat 1 — read the chart properly (30 s).**

> **"Left is survivors found, right is time to reach half of them. Three
> scenarios: a good prior, a mediocre one, and none at all."**
>
> **"With good prior information: twenty out of twenty, three point two times
> faster."**

**Beat 2 — the bottom row. Point at it deliberately. (30 s)**

> **"Now look at the bottom row. With no useful prior information, we find
> eleven. The grid finds eleven. We match it exactly — no advantage at all."**
>
> *(pause)*
>
> **"We're showing you that on purpose. We tested the case where our own method
> has nothing to offer, because that's the test that tells you whether the
> other two rows are real."**

**This is the highest-trust moment available to you in the entire presentation.**
Most teams would delete that row. Keep it, point at it, and let it work.

Then the benefits, fast — fifteen seconds, don't linger:

> **"Survivors reached sooner. A ranked queue instead of a list of dots. Works
> with no network. And it's a commodity drone plus one edge board — this is
> deployable by a state disaster response force, not just a research lab."**

---

### Slide 6 · References + close — 30 seconds

> **"Every dataset and tool here is public. Nothing bought, nothing
> proprietary. Our accuracy is measured on a held-out split of eighty-six
> thousand labelled people, and our latency comes from real Qualcomm hardware
> — medians of a hundred runs, not best case."**

Then close on the thesis you opened with:

> **"Search isn't a coverage problem. It's a decision problem. ARES is a drone
> that decides where to look next."**

Stop. Do not add "thank you, any questions?" in a rush — just stop, and let
them come to you.

---

## 4. The five questions you will get

Twenty seconds each. Rehearse these out loud; a confident short answer reads as
mastery, a long one reads as nerves.

**"Have you actually flown this?"**
> No. Everything perception-side is measured on real footage and real silicon.
> The planner is simulated. Flying it is next, and we'd rather tell you that
> than imply otherwise.

**"Where does the prior come from in a real deployment?"** — *your weakest
point; know it cold*
> Building density from OpenStreetMap, terrain from a DEM, flood extent from
> Sentinel-1 radar, and the locations of emergency calls. Today ours is
> synthetic and we sweep its quality as a parameter — which is exactly why we
> tested the zero-information case.

**"Is that your model's output, or a stock demo?"**
> Ours. The footage is from a public UAV dataset because we don't have an
> aircraft, but every box on screen is our model running. We'd never
> hand-draw a detection.

**"Why only three hazard classes?"**
> Because three are the ones we have per-class metrics for. We could list
> seven. We'd be guessing on four of them.

**"How is this different from search drones that already exist?"**
> Existing systems stream video to a human who decides where to fly. Ours
> decides, and the human supervises. That is the whole difference, and it's
> why the ranking has to be explainable rather than a black box.

---

## 5. Delivery — six things that matter more than the slides

1. **Pause after every big number.** Say it, then stop for two seconds. A
   number that runs straight into the next sentence sounds like filler. A
   number followed by silence sounds like evidence.

2. **One number per slide gets emphasis; the rest are support.** Slide 2 → the
   grid plateaus at 17. Slide 3 → 489 of 489. Slide 4 → what isn't built.
   Slide 5 → the bottom row. Never recite a table.

3. **Point at things.** When you say "look at the bottom row", physically point
   at the bottom row. Judges follow hands.

4. **Never read a slide out loud.** They read faster than you talk. The slide
   is the evidence; you are the argument.

5. **Say "we measured" not "we think".** Every time. You have earned it — this
   project's whole advantage is that the sentence is literally true.

6. **Rehearse the first thirty seconds until it's automatic.** Nerves are worst
   at the start. If the opening question comes out clean, the rest follows.

---

## 6. The three-minute compression

If you get cut short, drop these in this order: slide 6 → benefits on slide 5 →
the technical beats 1 and 2 on slide 3.

What must survive:

| | |
|---|---|
| **0:00** | The opening question and pause |
| **0:20** | The grid plateaus at 17, and the arithmetic why |
| **0:50** | The keys analogy — probability plus staleness |
| **1:15** | 489 of 489 on the NPU, and the 22-looks answer |
| **1:50** | The chart, including the bottom row |
| **2:30** | The scope table and *"a smaller system that's true"* |
| **2:50** | The thesis, restated. Stop. |

---

## 7. What makes this pitch different — say it out loud if you get the chance

Almost every hackathon pitch is a list of features that mostly work. Yours has
three things that are rare in a room, and it is worth knowing which they are:

- **An idea with a thesis**, not a feature list — search as a decision problem.
- **Numbers that are all real**, with the method stated, on real hardware.
- **A team that says what it didn't build**, before being asked.

The third one is the one judges remember. Lead with the work, close with the
honesty, and let the two reinforce each other.

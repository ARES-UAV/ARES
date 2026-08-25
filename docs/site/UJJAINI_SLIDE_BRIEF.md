# ARES — Slide Brief for Ujjaini

**From Dewang · 24 August 2026 · for the 7-slide SIH deck**

---

## Before you start

**Get the official template from the SPOC first.** SIH prescribes the section
headings, and the deck is rejected or marked down if you rename them. Everything
below is *content to drop into whatever boxes the template gives you* — not a
layout to build from scratch.

The two rules that matter more than anything else here:

**One idea per slide.** SIH evaluators move fast. A slide with six bullets gets
read as zero. Every slide below has one thing on it and everything else is
support.

**Do not change a number.** Every figure in this brief is measured. If something
looks wrong or you want a rounder number, ask me — do not adjust it. A number
that does not match the dashboard is the fastest way to lose a judge.

---

## SLIDE 1 — Title

**On the slide:**

- **ARES** — Autonomous Rescue & Environmental Intelligence System
- Problem statement ID and title (from the SIH portal)
- Team name, institute
- Team members

**Add a QR code** linking to the website. Bottom-right, small. Judges on phones
will scan it; nobody types a URL.

**Visual:** one still from the demo clip with detection boxes drawn on it. Dark
background. Nothing else.

---

## SLIDE 2 — Idea / Proposed solution

### The one thing on this slide

```
7,081  →  333  →  23
```

**Raw detections → track identities → confirmed survivors.**

Make it big. This single graphic states the problem *and* the solution at once,
and it is the most memorable thing in the deck.

### Supporting text — use close to these words

> A drone camera over a disaster zone produces thousands of detections. A rescue
> coordinator needs one number: how many people are down there, where they are,
> and who to reach first.
>
> ARES runs detection, tracking, mapping and priority ranking **on the aircraft**,
> and sends back a few kilobytes of structured data instead of a video stream.

### The line to include if there is room

> Offline resilience is not a feature we added — it is a consequence of running
> the analysis onboard. Losing the network costs us the video feed and nothing
> else.

**Do not** put the tech stack on this slide. That is slide 3.

---

## SLIDE 3 — Technical approach

### The one thing on this slide

The four-stage pipeline diagram. **Copy it from the website** (the "Four stages"
section) — it is already drawn.

```
DETECTION  →  TRACKING  →  LOCALIZATION  →  PRIORITY  →  DASHBOARD
YOLOv12s      ByteTrack     nadir            weighted
@ 960 px      persistent    projection       formula
conf 0.18     track IDs     1.8 cm/px
```

### One line under each stage — no more

| Stage | Line |
|---|---|
| Detection | YOLOv12s trained on combined C2A + VisDrone, single `person` class |
| Tracking | ByteTrack assigns persistent IDs so nobody is counted twice |
| Localization | Pixel offset → GPS from known altitude and field of view |
| Priority | A transparent weighted formula — confidence, cluster size, hazard proximity |

### The technical point worth making

> The four stages exchange one JSON format. That decouples three people's code —
> and it lets the demo replay a stored file rather than running inference live.

**Stack, in small type at the bottom:** Python · FastAPI · Pydantic · React ·
Vite · Leaflet · OpenStreetMap · ONNX Runtime. **No API keys anywhere.**

---

## SLIDE 4 — Feasibility and viability

### This is our differentiator. Give it the honest table.

Most teams claim every capability in the problem statement. We do not, and
saying so out loud is what makes the rest of the deck credible.

| Capability | Status |
|---|---|
| On-device AI inference | **Built** |
| Survivor counting & tracking | **Built** |
| Geo-tagged mapping | **Built** |
| Emergency alerting / priority | **Built** |
| Command centre dashboard | **Built** |
| Offline resilience | **Built** |
| RGB + thermal fusion | *Partial* — public datasets, not hardware |
| Hazard classification | *Partial* — 3 of 7 classes, Phase 2 |
| Autonomous navigation, SLAM | **Described only** — architecture, not code |

**Colour the three states differently.** Built, partial, described. Do not use
red for "described only" — it is a deliberate scoping decision, not a failure.

### The sentence that carries the slide

> We would rather answer hard questions about what is on the screen than have a
> judge discover that half of it is a mock-up.

### Risks — one line each, if the template asks for them

- **No physical drone.** Demo footage is a public UAV dataset; the detections are
  our own model's real output over it.
- **Edge throughput.** A Pi 4 running an attention-based model is slow. Covered
  on slide 6.
- **Identity switches after occlusion.** Known, quantified, and stated on the
  dashboard rather than hidden.

---

## SLIDE 5 — Impact and benefits

### The one thing on this slide

```
Recall 0.740  →  0.831
```

**+91 more survivors found per 1,000 present.**

### The words

> Most detectors run at a confidence threshold of 0.5, balancing false alarms
> against misses. Search and rescue is not a balanced problem.
>
> **A false alarm costs a rescuer thirty seconds of walking. A missed survivor
> cannot be recovered.**
>
> We run at 0.18, chosen off the precision-recall curve from our validation run.
> That is ninety-one more people found for every thousand present.

That is the strongest thing in the entire deck. Give it room. Do not crowd it
with other statistics.

### Secondary impact points — small, one line each

- Works with no network. The analysis is already done onboard.
- Runs on a ₹5,000 single-board computer, not a ground station.
- The priority ranking is a formula a coordinator can read, not a black box.

---

## SLIDE 6 — Prototype

### Split the slide in two

**Left — the dashboard.** One screenshot, large. Do not put four small ones.

**Right — three figures and the FPS argument.**

| | |
|---|---|
| Precision | **0.845** |
| Recall | **0.717** |
| mAP50 | **0.775** |

*(Dewang will send the measured Pi FPS figure before you finalise. If it has not
arrived, write "benchmark in progress" — do not estimate it.)*

### The FPS line, which you will be asked about

> At 20 metres altitude the camera sees 23 metres of ground, so the aircraft
> takes several seconds to cross its own footprint. Every patch is visible in
> several consecutive frames even at 1 FPS. **A search UAV does not need 30 FPS —
> it needs to not miss the ground.**

Have that memorised. It converts the deck's weakest-looking number into evidence
that we understand the system.

---

## SLIDE 7 — Research and references

- **Datasets:** C2A (disaster-scene humans), VisDrone-VID (UAV benchmark), AIDER
  (hazard classification, Phase 2)
- **Model:** YOLOv12 — *Attention-Centric Real-Time Object Detectors*,
  arXiv:2502.12524
- **Tracking:** ByteTrack
- **Mapping:** OpenStreetMap

**Then the website link and the QR code again**, this time large. This is where a
judge who wants depth goes.

---

## What to leave off entirely

| Leave off | Why |
|---|---|
| Anything about SLAM working | It is architecture only. Claiming it undoes slide 4 |
| A battery / GPS / telemetry mock-up | There is no aircraft. One question destroys it |
| Any invented hazard on the map | The classifier does not exist yet |
| "95% accurate" or any single accuracy figure | Precision and recall are different numbers and judges know it |
| Stock photos of drones | We have real footage with real detections. Use that |
| A slide of code | Nobody reads code on a projector |
| The word "revolutionary" | And "cutting-edge", and "state-of-the-art" |

---

## Design notes

**Colours — take them from the dashboard so the deck and the product match:**

```
Background   #0B1013   near-black, slight cool-green
Panels       #121A1E
Text         #E6EDEF   not pure white — it glares on a projector
Accent       #22A7BD   cyan. Survivor detections only
Priority     #FFCE9E → #FB9A4A → #E06A1F → #A8410C   light to dark
```

**Cyan means "a detection" and nothing else.** Do not use it for headings or
body text.

**No green anywhere.** The lowest-priority person in a disaster zone still needs
rescuing, and a green anything says otherwise.

**Every number in a monospace font.** It reads as an instrument reading rather
than a claim.

**Test it projected.** Thin light text on dark backgrounds disappears on a
low-contrast projector. Check from the back of a room before the 5th.

---

## What I owe you

- [ ] Three dashboard screenshots (full view, map + queue, detection overlay)
- [ ] The demo clip with detection boxes, for slide 1
- [ ] The measured Raspberry Pi FPS number, as soon as the SD card arrives
- [ ] The website URL and a QR code for it

Ping me if any number in this brief looks wrong. Do not adjust one yourself —
every figure here matches what is on the dashboard, and they have to stay
matching.

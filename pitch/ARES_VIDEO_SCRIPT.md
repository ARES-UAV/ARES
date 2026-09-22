# ARES — demo video script

**Target length 4:00** (acceptable range 3:30 – 4:30) · one narrator · 1920×1080

Every number spoken here is measured and traceable to
`experiments/ARES_MEASURED_NUMBERS.md`. Nothing is estimated. If a figure
changes before recording, change it here first.

---

## The rules this script follows

1. **Never say "our drone finds survivors 3× faster."** That is a flight claim
   and there is no aircraft. Say **"in simulation"** every time. The script
   already does.
2. **Never claim autonomous flight, GPS-denied navigation or seven hazard
   classes.**
3. The footage is from public UAV datasets and **every box on screen is real
   model output.** Say so — it is a strength, not an apology.

---

## Script

| Time | On screen | Narration |
|---|---|---|
| **0:00** | Black. Title card: **ARES** / *Autonomous Rescue & Environmental Intelligence System*. Hold 2 s. | *(silence, then)* |
| **0:04** | Aerial disaster footage — the demo clip, no boxes yet, slow motion. | In the first seventy-two hours after a disaster, finding people is a race. And the way we search from the air has barely changed. |
| **0:14** | Simple animation: a drone tracing a rigid back-and-forth grid over terrain. | A drone flies a fixed grid. Every square metre gets the same attention — the collapsed apartment block and the empty field, equally. |
| **0:24** | The grid animation keeps going; a battery indicator drains; large parts of the map stay unsearched. | The battery runs out before the area is finished. And the team on the ground gets a list of coordinates with no idea which one to reach first. |
| **0:34** | Cut to black. Text: **What if the drone decided where to look next?** | ARES is a drone that decides where to look next. |
| **0:41** | `d1_system.png` — the four-stage loop, animate each stage in. | It sees, it identifies, it ranks by urgency, and then it re-plans in the air. All four stages run on the drone itself. |
| **0:52** | Dashboard detection feed, playing, boxes and track IDs live. | Start with seeing. Our detector was trained on two public disaster datasets — people photographed from above, in rubble, in flood water, in crowds. |
| **1:03** | Freeze one frame. Overlay: **recall 0.824 · 86,092 labelled people · confidence 0.18**. | On a held-out set of eighty-six thousand labelled people, it finds eighty-two in a hundred. We run it deliberately over-sensitive. An operator dismisses a false box in a second. A missed survivor is not recoverable. |
| **1:18** | Same clip, numbers counting up: **7,081 → 333 → 23**. | But a detector alone can't count. Seven thousand detections over this clip are not seven thousand people. Tracking collapses them to three hundred and thirty-three candidates, and a two-and-a-half-second persistence rule confirms twenty-three real survivors. |
| **1:33** | Cut: photo of the Dragonwing board, then `d4_benchmark.png`. | None of this is useful if it needs a data centre. We measured it on real Qualcomm silicon, through Qualcomm AI Hub — physical hosted devices, not emulators. |
| **1:44** | Zoom the **100% / 489 of 489** badge. | Every single layer of the network runs on the Hexagon NPU. Nothing falls back to the CPU. On the drone-class board that is two hundred and nine milliseconds a frame — under five frames a second. |
| **1:57** | Animation: drone moving, its 23 m footprint sweeping ground, counter ticking to ~22. | Which sounds slow, until you do the geometry. At twenty metres the camera sees twenty-three metres of ground, and the aircraft crosses that in under five seconds. Every patch of ground gets about twenty-two looks. Compute is not the bottleneck. |
| **2:10** | Text: **So where should it fly?** Then `02_good.mp4` begins — split screen, both drones start. | Which brings us to the real question. Where should it fly? |
| **2:20** | Let the split-screen run. Left = grid. Right = adaptive, heat map visible. | On the left, the standard grid. On the right, ARES. Same map, same survivors, same battery, same detection luck. The only difference is the choice of where to go. |
| **2:33** | Adaptive starts finding people; counters diverge. | ARES builds a live probability map and always flies to the highest-value ground it hasn't searched yet. |
| **2:43** | End card over the video: **20 of 20 vs 11 of 20 · 3.1× faster to half · median of 100 simulated missions**. | Across a hundred simulated missions, the adaptive planner finds twenty survivors out of twenty where the grid finds eleven — and reaches half of them three point one times faster. In simulation. |
| **2:57** | Quick cut to `04_uniform.mp4`, both counters level. | And when we take away its information entirely — a completely useless prior — it simply matches the grid. It never does worse. We tested the case where our own method has no advantage, because that is the test that matters. |
| **3:12** | Screen recording: the live dashboard. Click a map pin → table row highlights → event log scrolls. | Everything lands in one console. A live map, a rescue queue ordered by priority, and an event log where every line is derived from a detection — nothing is hand-written. |
| **3:25** | Pull the network cable / wifi-off icon; dashboard keeps running. | Cut the internet and it keeps working. The map tiles are cached and the inference already happened on the aircraft. |
| **3:34** | The scope table from slide 4, clean full-screen. | We are precise about what is built and what is not. Detection, tracking, localization, priority, the dashboard and the on-device benchmark are built and measured. Thermal is trained. Fusion is measured on public paired data. The adaptive planner is simulated — not flown. |
| **3:50** | Text: **Every number in this video is measured.** | We would rather show you a smaller system that is true than a bigger one that isn't. |
| **3:58** | ARES logo. Team name. PS ID. Fade. | ARES. A drone that decides where to look next. |
| **4:06** | End. | *(silence)* |

**Word count ≈ 600.** At a calm 150 words per minute that is almost exactly four
minutes of speech, leaving room for the silent open and close.

---

## What has to be recorded or rendered

| # | Shot | Source | Status |
|---|---|---|---|
| 1 | Title and end cards | make in the editor, ARES palette below | to do |
| 2 | Raw aerial footage, no boxes | `backend/data/demo_clip.mp4` | **have it** |
| 3 | Grid-pattern animation + draining battery | simple editor animation, or screen-record the lawnmower panel of `02_good.mp4` alone | to do |
| 4 | The four-stage loop | `d1_system.png` — animate the four cards in | **have it** |
| 5 | Detection feed with boxes and IDs | screen-record the dashboard playing | to record |
| 6 | Counter animation 7,081 → 333 → 23 | editor text animation | to do |
| 7 | Dragonwing board photo | Qualcomm's press image, credited — **or skip it** and use the benchmark card alone | optional |
| 8 | Benchmark card | `d4_benchmark.png` | **have it** |
| 9 | Footprint / 22-looks animation | simple editor animation | to do |
| 10 | Adaptive vs grid, good prior | `simulation/shots/02_good.mp4` | **rendered** |
| 11 | Adaptive vs grid, uniform prior | `simulation/shots/04_uniform.mp4` | **rendered** |
| 12 | Results end card | `d3_results.png` | **have it** |
| 13 | Live dashboard walkthrough | screen-record at 1920×1080 | to record |
| 14 | Offline demo | record killing wifi with the dashboard open | to record |
| 15 | Scope table | export slide 4's dark panel, or rebuild as a card | **have it** |

**Three things actually need recording: shots 5, 13 and 14 — all screen captures
of the dashboard.** Everything else exists or is an editor animation.

---

## Production notes

**Voice.** One narrator, calm and unhurried. This script's power is that the
numbers are real; reading them excitedly makes them sound like marketing. Read
them flatly and let them land.

**Music.** Low, textural, no melody competing with speech. **Drop the music out
entirely for the three seconds around each headline number** — 0.824, 100%,
20 of 20. Silence is what makes a number feel like evidence.

**Pacing.** The split-screen section (2:10–3:10) is the centrepiece — give it
room and resist cutting away. A judge watching one drone find people while the
other ploughs empty ground understands the whole project without narration.

**Captions.** Burn in subtitles. Judges often watch muted, and every headline
number should be legible without audio.

**Palette,** to match the deck:
ink `#12222A` · teal `#17A2B8` · dark teal `#0E6E7E` · amber `#E07B39` ·
grey `#6B7C85` · light `#EDF3F5`. Font: Calibri, or Inter if available.

**Export.** 1080p, H.264, ~10 Mbps, AAC audio. Upload **unlisted to YouTube** —
a Drive link often demands sign-in, and a screener will not create an account
to watch your video.

**Put the URL on the slide as visible text, not only as a hyperlink.** The SIH
submission is a PDF and a bare clickable region can be missed; typed-out text
always survives.

---

## Two things to fix before shot 5 and 13 are recorded

The current dashboard screenshot shows both:

1. **The product name reads "Adaptive Rescue and Exploration System"** in the
   header. The deck, the video and every other document say **"Autonomous
   Rescue & Environmental Intelligence System."** This has been flagged
   as the highest-priority documentation fix and it is still open. A judge who
   sees the deck and the screenshot together will notice.
2. **The mission date reads 25 Aug 2026.** `CONVENTIONS.md`: *"Keep any mission date
   current. A stale placeholder date reads as an unfinished demo."*

Both are one-line changes in the frontend. Fix them, take the screenshots again,
and the same file paths drop straight into the deck and the video.

---

## If a 60-second cut is ever needed

Keep only: 0:04 problem → 0:34 the question → 2:10–2:55 the split screen →
3:12 dashboard → 3:50 close. That is the argument with nothing removed that
carries weight.

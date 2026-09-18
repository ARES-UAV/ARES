# ARES — SIH 2026 Idea PPT · everything in one place

**Files:** `ARES_SIH2026_Idea_Presentation.pptx` (edit this) ·
`ARES_SIH2026_Idea_Presentation.pdf` (this is what gets uploaded)

The deck is already written, designed and filled with real numbers. Six slides,
which is the SIH maximum. Nothing here needs a developer.

---

## 1. The five things you must fill in

Everything else is done. These five are the only blanks:

| Where | What | Where to get it |
|---|---|---|
| Slide 1 | Problem Statement ID | SIH portal |
| Slide 1 | Problem Statement Title | SIH portal — **paste it exactly**, do not reword |
| Slide 1 | Theme | SIH portal (likely *Disaster Management*) |
| Slide 1 | Team ID + Team Name | SIH portal — must match the registration exactly |
| Every slide | The "Your Team Name" oval, top-left | your registered team name |

Slide 4 also has an orange box of **numbers still being measured**. If those
land before submission, replace the brackets. If they don't, leave them —
saying "measurement in progress" is normal and honest. Do **not** invent a
number to fill a bracket.

---

## 2. The rules SIH sets, which this deck already follows

- **Maximum 6 slides including the title.** This deck is exactly 6. Do not add one.
- **Upload a PDF.** No PPT, DOC or anything else is accepted.
- **Points, diagrams and infographics — not paragraphs.** Already done.
- **The template's section titles must stay.** IDEA TITLE has been replaced with
  our actual idea title (that one is meant to be replaced); TECHNICAL APPROACH,
  FEASIBILITY AND VIABILITY, IMPACT AND BENEFITS and RESEARCH AND REFERENCES are
  unchanged, as required.
- The SIH logo, footer bar and slide numbers are untouched.

---

## 3. What is on each slide, and the line to say out loud

### Slide 1 · Title
Just the portal fields plus our project name.

### Slide 2 · The idea
Three cards — the problem, our solution, why it is different — then a four-stage
loop diagram, then three measured numbers.

> *"After a disaster, search drones fly a fixed grid. Every patch of ground gets
> equal time, including empty ground, and the battery runs out before the area
> is covered. Our drone reads the scene while it flies and re-plans in the air.
> It finds 20 survivors out of 20 where a fixed grid finds 11, and reaches half
> of them 3.2 times faster."*

The orange arrow underneath the diagram is the whole idea: **what the drone sees
changes where it flies next.**

### Slide 3 · Technical approach
Technology chips along the top, then the full architecture.

> *"Two cameras feed a fusion step, then tracking makes sure each person is
> counted once. Everything above the dark bar runs on the drone itself. The dark
> bar is the single data format our three sub-teams agreed on. Below it is the
> ground station, which also works with no internet."*

### Slide 4 · Feasibility and viability
Left: six things already built and measured. Right: risks and how we handle
them, plus what is still being measured. Bottom: the scope table.

> *"We separate what is built, what is partial and what is only simulated. Every
> number on this slide was measured — none of it is estimated."*

**This is the slide that wins trust.** Teams that overclaim get caught in
screening; teams that scope honestly and show measurements do not.

### Slide 5 · Impact and benefits
The results chart, then three benefit cards.

> *"Left is survivors found, right is how long it took to reach half of them.
> Look at the bottom row: with no useful prior information our method simply
> matches the grid. It never does worse. We tested the case where our own method
> has no advantage, which is why the other two rows can be believed."*

### Slide 6 · Research and references
Datasets, tools and method — all public, all open. The dark strip explains how
the numbers were produced, which is the first thing a technical screener asks.

---

## 4. The numbers on the deck, and what each one means

Use these if you are asked. Every one is measured, not estimated.

| Number | Means |
|---|---|
| **recall 0.824** | Of every 100 people in the test images, the model finds 82. Measured over 86,092 labelled people. |
| **20 / 20 vs 11 / 20** | Survivors found in one 20-minute flight, median of 100 simulated missions. |
| **3.2× faster** | Time to reach half the survivors: 291 seconds vs 935. |
| **209 ms · 4.8 FPS** | One frame on the real Qualcomm drone board. About 22 looks at every patch of ground — plenty for search. |
| **489 of 489 layers on the NPU** | 100% of the model runs on the drone's AI chip, nothing falls back to the slow CPU. **This is the headline, not the frame rate.** |
| **7,081 → 333 → 23** | Raw detections, then tracks, then actual unique survivors. Shows we don't count the same person twice. |
| **thermal recall 0.883** | The thermal model on 12,686 aerial thermal images — this is the night and smoke capability. |

---

## 5. Things not to say

- Do **not** say "our drone finds survivors 3× faster." There is no aircraft
  yet. Say **"in simulation"** — the deck already words it that way.
- Do not claim autonomous flight or seven hazard classes.
- Do not upgrade anything on the scope table from *partial* or *simulated* to
  *built*.

If a judge pushes on any of this, the honest answer is strong: *"we measured
what we could and labelled the rest."*

---

## 6. If you want to change the look

The three diagrams are images (`d1_system.png`, `d2_pipeline.png`,
`d3_results.png`). They can be regenerated at any size or colour — ask, and
you'll get new versions to drop in. Everything else is normal PowerPoint text
you can edit directly.

Colours used, if you need them elsewhere:
deep ink `#12222A` · teal `#17A2B8` · dark teal `#0E6E7E` · amber `#E07B39` ·
grey `#6B7C85` · light panel `#EDF3F5`. Font is Calibri throughout.

---

## 7. Before you upload

- [ ] All five portal fields filled on slide 1
- [ ] "Your Team Name" oval replaced on all six slides
- [ ] Pending numbers on slide 4 either replaced or left honestly bracketed
- [ ] Exported to **PDF** — File → Save As → PDF
- [ ] Opened the PDF and checked all six pages render
- [ ] Still exactly six slides

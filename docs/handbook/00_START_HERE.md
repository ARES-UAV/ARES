# The ARES Handbook

**Everything in this project, explained from zero.**
Written 24 August 2026, twelve days before the internal hackathon.

---

## Why this exists

You built a working UAV search-and-rescue system. It came together across
weeks of reading, experiments that failed, and arguments you won't remember in
two weeks.

A judge is going to point at a number on your screen and ask where it came
from. "It was already like that" does not survive that moment. This handbook
exists so that every number, every file and every decision in ARES is something
you can explain in your own words.

It is also a course. If you read it front to back you will come out
understanding object detection, multi-object tracking, coordinate projection,
REST APIs and React — not at expert level, but at the level where you can read
the next thing yourself.

---

## Watch it first, if you would rather

Four recordings of the system running. They cover the same ground as Parts 1,
3, 5 and 7, in about twenty minutes instead of a day.

| | Video | Handbook parts it covers |
|---|---|---|
| 01 | [The case for ARES](https://youtu.be/J89oZT977GU) | Part 1 |
| 02 | [The adaptive planner](https://youtu.be/nnc5-N-GEU4) | Part 6, and `simulation/RESULTS.md` |
| 03 | [Detection to GPS](https://youtu.be/das3HfpK2vY) | Parts 2, 3 and 6 |
| 04 | [The command dashboard](https://youtu.be/VloJFoPbxy4) | Parts 5 and 7 |

The site is at <https://ares.paralux.in>, the source at
<https://github.com/ARES-UAV/ARES>.

---

## How to read it

**If you have twelve days and a demo:** read Part 1, then Part 10 (Judge Q&A),
then Part 9 (Decision log). That is the minimum to defend the project. Come
back for the rest afterwards.

**If you want to actually learn this:** read in order. Parts 1–4 are the
machine learning half, Parts 5–7 are the software half, and neither assumes you
have read the other.

**If you are looking something up:** Part 5 and Part 7 are file-by-file
references. Part 12 is a glossary of every term used anywhere in the project.

---

## The parts

| Part | What it covers |
|---|---|
| **1** | What ARES is, the four-stage pipeline, and why each stage exists |
| **2** | Machine learning and YOLO from zero — every training term, your actual numbers |
| **3** | Tracking, de-duplication, and the two bugs that nearly sank it |
| **4** | ONNX, export, and on-device benchmarking |
| **5** | The backend, file by file and function by function |
| **6** | The mathematics, derived rather than asserted |
| **7** | The frontend, file by file |
| **8** | The tools directory and every command you ran |
| **9** | Decision log — what you chose, what you rejected, and the mistakes |
| **10** | Judge Q&A and the honest-scope script |
| **11** | Learning path — what to study next and where |
| **12** | Glossary |

---

## Three rules this project runs on

You will see these referenced throughout. They are not style preferences; each
one was arrived at after something went wrong.

**1. Never fabricate data.**
No hand-authored detections, no invented hazards, no plausible-looking FPS
number. If a judge asks "is this your model's output?" the answer has to be
yes. This is why `HAZARDS` is an empty list and `DEVICE_FPS` is `None` — both
of which make the dashboard *less* impressive and *more* defensible.

**2. Agreeing is not the same as being one number.**
Two panels that both count survivors will eventually disagree. The fix is never
to make the two calculations match — it is to delete one of them so there is
only ever one number. You will see this pattern everywhere in the frontend.

**3. Prefer boring and working.**
This codebase has twelve days to live before it is judged. Every choice trades
in favour of working on demo day over impressive-but-fragile.

---

## A note on the code comments

Your backend is unusually heavily commented — often ten lines of reasoning
above three lines of code. That is deliberate and it is a deliberate *gift to
you*. When a judge asks about `MIN_TRACK_SECONDS`, the answer is already
written above the constant. This handbook expands on those comments and adds
the background they assume; it does not replace them.

Read the code alongside this. The comments are the primary source.

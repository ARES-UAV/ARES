# ARES — plan to 30 September

**Revision 2 · 5 September 2026.** Replaces revision 1 of this morning after
five corrections from Dewang.

| | |
|---|---|
| Internal hackathon | 10 September |
| **SIH portal submission** | **30 September — confirmed** |
| Our submission target | **28 September** |
| Team | 6, in three groups |
| Faculty mentor | **secured** |

---

## What changed since revision 1

| | Revision 1 said | Actually |
|---|---|---|
| Deadline | 30 Sept, estimated | **Confirmed.** Target the 28th anyway — portals fall over on deadline day |
| `tests/` | "rebuild the suite" | **Wrong fix.** See below |
| Faculty mentor | the run-ending risk | **Closed** |
| Shape of the plan | close gaps, submit | Gaps take 2–3 days. **The rest of the month builds something new** |
| Roles | six individuals | **Three groups of two** |

### On `tests/` — what actually happened

Robin wrote the suite and ran it: `REPORT.md` §14's *"60 passed"* is a real run
on his machine. What I checked during the merge review was his **code**, and it
was correct — that review stands.

But the `Rob` branch never contained `tests/`. The merge brought exactly eleven
files (`REPORT.md`, `TO-DO/*`, four backend modules, two frontend files,
`tokens.css`, `requirements.txt`) and no test directory, so the files were never
pushed rather than lost in the merge.

**The fix is Robin running `git add tests/ && git push`, not anyone rewriting
anything.** Two minutes. It is task 0 in the G2 brief.

---

## The shape of the month

**6–10 September — the internal.** Feature freeze. Ship what exists.

**11–24 September — build the new thing.** Two weeks, three groups, running in
parallel. This is where the extra people pay for themselves.

**25–28 September — freeze, audit, submit.**

### What we are building that is new

The four components all work and **have never run as one system.** The detector
runs offline over a video; the planner runs in an abstract grid with no camera
in it. So the honest answer to *"does this work end to end?"* is currently no.

G3 closes the loop in **ArduPilot SITL** — a real flight stack, real vehicle
dynamics — with a camera that renders the aircraft's true view by cropping a
real georeferenced aerial photograph. G1 supplies perception, G2 supplies
telemetry-driven localization and a live dashboard.

Three things fall out of that, and each is worth more than any feature:

1. **A measured localization error.** People sit at known GPS positions, so
   there is ground truth for the first time. The project has never measured
   this — `REPORT.md` says so.
2. **The biggest assumption disappears.** Altitude, heading and origin are fixed
   constants today, disclosed as assumed. In SITL they stream from the flight
   controller — which also makes the SIH IMU+GPS fusion requirement literally
   true rather than architecturally true.
3. **The weakest scope row moves.** "Autonomous navigation — described only"
   becomes "flown in simulation on a real flight stack, not flown on hardware."

Details, tiers and the gates are in `planning/G3_DRONE_SIM.md`.

> **Hard gate: if SITL is not flying waypoints by 14 September, the loop is
> cut** and everyone moves to fusion, hazards and the deck. Say it out loud on
> the 14th. Setup problems either resolve in days or do not resolve.

---

## The three groups

Full briefs, one per group, each self-contained with the context that group
needs:

| | Owns | Brief |
|---|---|---|
| **G1** | Models and detection — fusion, hazard classifier, INT8, perception for the loop | `planning/G1_AI_MODEL.md` |
| **G2** | Geometry, scoring, API, dashboard — telemetry localization, error measurement, live mode | `planning/G2_BACKEND_FRONTEND.md` |
| **G3** | Flight simulation and delivery — SITL, the camera, the loop; plus video and deck | `planning/G3_DRONE_SIM.md` |

Each brief carries: what to build, why it matters, the context to read first,
concrete commands, a done-when test, and a what-not-to-do list. **None of them
contains cleanup of past work** — that is Dewang's list below.

The dependencies are few and all one-way:

```
G1 perception ──► G3 loop ──► G2 live mode
G1 hazard classes ──► G2 planner risk term
G3 known GPS positions ──► G2 error measurement
```

Nobody waits on anybody for their first week of work.

---

## Dewang's own list — the past-work cleanup

Not given to the groups. Most of these are minutes, not days.

| | Task | Time |
|---|---|---|
| 1 | **Commit the 31 August work.** 12 untracked paths including `render_video.py`, `multi_sortie.py`, the fusion and thermal docs, and `simulation/shots/` holding both rendered mp4s. Git does not know they exist | 10 min |
| 2 | **Back the two mp4s up off the laptop** — Drive or a Release. They are the demo video | 5 min |
| 3 | Ask Robin to push `tests/` | 2 min |
| 4 | **Fix the project name.** `README.md` says *Adaptive Rescue and Exploration System*; everything else says *Autonomous Rescue & Environmental Intelligence System*. This is the highest-priority doc fix and a screener reading both will notice | 5 min |
| 5 | README's Repository Structure line still says `simulation/` holds documentation only — it holds a 100-seed benchmark | 10 min |
| 6 | `Rob-Todo.md` header still says "cutoff 5 September" | 2 min |
| 7 | Generate the missing `docs/img/disaster-detections.png` — same weights, conf 0.18, imgsz 960, over a handful of C2A images. The site block is a placeholder | 20 min |
| 8 | Publish the thermal weights to a Release *(also G1 task 0 — do whichever is faster)* | 20 min |
| 9 | Random-search baseline, the third line on the planner chart | 1 hr |
| 10 | **Full dry run** — clean clone, wifi off, backend killed | 1 hr |

Items 1 and 2 are today. A laptop failure right now costs a day of work and the
demo video.

### Status, 29 September

| | Outcome |
|---|---|
| 1 | Done — the 31 August work is tracked. |
| 3 | Not done. `tests/` was never pushed; there is no test suite in this repository and the README does not claim one. |
| 4 | Done. Settled on **Autonomous Rescue & Environmental Intelligence System** and the two outliers were changed to match. See `CONVENTIONS.md`. |
| 5 | Done — the structure block now describes what is actually in each directory, and says which ones hold code rather than documentation. |
| 6 | Moot — `Rob-Todo.md` is not in the repository. |
| 7 | Resolved differently. The figure was never generated, so the claim was removed rather than left as a placeholder: the site now points at `experiments/Perception/C2A/` instead of promising a picture. |
| 9 | Not done. The planner chart has two lines, not three. A random-search baseline remains the obvious next control. |

Item 10's dry run is what produced the rest of this list: `simulation/run.py`,
`world.py` and `check_baseline.py` were all run from a clean checkout on a
different machine on 29 September. `check_baseline.py` crashed on a signature
mismatch and `run.py`'s default was still 30 seeds, so the documented command
reproduced a different table from the published one. Both are fixed.

```bash
cd ~/College/ARES
printf 'simulation/frames/\nsimulation/shots/\n' >> .gitignore
git add .gitignore simulation/*.py simulation/*.md simulation/lab_traces.json \
        simulation/results/multi_sortie.json \
        experiments/SENSOR_FUSION.md experiments/FUSION_PLAN.md \
        experiments/THERMAL_MODEL.md tools/fuse_eval.py
git rm --cached fix_position_spread.py 2>/dev/null; git add -u
git commit -m "Multi-sortie campaign, video renderer, fusion and thermal analysis"
git push
```

The one item worth reconsidering: **#9's map-error check is superseded** if G3's
T2 lands, because that measures error against known ground truth over every
survivor instead of one pin against Google Maps. Keep it as the fallback if the
loop is cut on the 14th.

---

## Calendar

| Dates | G1 | G2 | G3 |
|---|---|---|---|
| **6–10 Sep** | *internal hackathon — feature freeze, no merges 8–10* |||
| 11–13 | thermal weights + provenance; **start LLVIP downloads** | push tests; telemetry localization | **T1 — SITL flying waypoints** |
| **14** | — | — | **GATE: T1 flies or the loop is cut** |
| 14–17 | fusion wired; LLVIP fine-tunes | error-measurement harness | **T2 — camera renderer** |
| 18–21 | hazard classifier + per-class metrics | planner risk term; 100 seeds re-run | **T3 — loop closed**; deck starts |
| 22–24 | INT8 accuracy; perception for the loop | live mode; routes on the map | T4 — live feed; video re-cut |
| **25** | *content freeze — every number audited against `ARES_MEASURED_NUMBERS.md`* |||
| 26–27 | *mentor and one outsider read the deck cold* |||
| **28** | **submit** |||
| 29–30 | *buffer — touch nothing unless the portal rejects something* |||

---

## Still not doing

Decided already; repeated so nobody re-opens them in week three.

| | Why |
|---|---|
| Claiming autonomous flight | Simulated is simulated. Saying so is why the other claims are believed |
| Seven hazard classes | Three, with per-class metrics |
| Early (4-channel) fusion | Late fusion uses the models that exist, degrades gracefully, and is explainable |
| Rewriting git history | A broken clone before a deadline beats 53 MB saved |
| Hand-authored detections or hazards | Ends the honest-scoping story, which is the project's strongest asset |
| Submitting on the 30th | Portals fall over on deadline day |

---

## The rule that has been worth the most

Every correction here came from re-reading an artefact instead of trusting a
note — the epoch 44→58 error, the `bytetrack-wide` false fix, the multi-sortie
counter bug, the `.hero` class collision, and today's `tests/` question, which
turned out to be a push that never happened rather than the missing suite it
looked like.

**Check the artefact. Then write the correction down.**

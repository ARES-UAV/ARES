# G3 — Drone, Flight Simulation & Delivery

**Owner:** 2 people (Lane A technical, Lane B is Ujjaini) · **Window:** 6 – 27 September

**You own the biggest new thing this project is building.** Everything else on
the schedule is closing gaps. This is new capability.

---

## Lane A — the closed loop

### What we are building, and why it matters

ARES has four components, each measured and each working:

| | proven |
|---|---|
| Detector | 0.774 recall on 86,092 instances |
| Tracker | 7,081 detections → 23 unique survivors |
| Localizer | pixel + GPS + IMU → lat/lon |
| Adaptive planner | 20/20 found vs the lawnmower's 11/20 |

**They have never run as one system.** The detector runs offline over a video.
The planner runs in an abstract grid with no camera in it. If a judge asks *"does
this actually work end to end?"*, today there is no answer.

You are going to make the loop close:

```
        ArduPilot SITL — a real flight stack, real vehicle dynamics
                    │  streams true position + attitude + battery
                    ▼
        camera renderer  — crops the aircraft's real view out of a
                           georeferenced aerial photograph
                    │  frames
                    ▼
        G1's detector + tracker
                    │  detections.json  (contract unchanged)
                    ▼
        G2's localize.py — now fed REAL telemetry, not constants
                    │  lat / lon
                    ▼
        belief update  →  adaptive planner  →  next target cell
                    │  MAVLink waypoint
                    └──────────────► back to the flight stack
```

**Four things this buys, in order of value:**

1. **A measured localization error.** Your world places people at *known* GPS
   positions, so for the first time there is ground truth to compare against.
   The project has never measured this. Its own guide says *"a measured error is
   worth ten claimed features."*
2. **The biggest assumption in the project disappears.** Altitude, heading and
   GPS origin are currently fixed constants, disclosed as assumed, because there
   is no aircraft. In simulation they stream from the flight controller.
3. **The weakest row in the scope table moves.** "Autonomous navigation —
   *described only*" becomes "flown in simulation on a real flight stack, not
   flown on hardware." That is an honest upgrade against the one SIH requirement
   this project currently cannot answer.
4. **New video.** A drone actually flying and actually finding people, instead
   of an abstract grid.

### The one design decision that makes or breaks this

**Do not use Gazebo's built-in human models.** The detector was trained on real
aerial photographs (C2A + VisDrone). Rendered low-poly people look nothing like
that, recall will collapse, and it will look like a model failure when it is a
rendering failure.

**Instead: render from a real aerial photograph.** Take one large georeferenced
aerial image of a flood-plain or open area. Composite real person image crops
into it at chosen GPS positions. Then "the camera" is a crop-and-warp out of
that image, given the aircraft's position and attitude:

```
aircraft at (lat, lon, alt, heading, roll, pitch)
   → compute the ground quadrilateral the camera sees
   → sample that region out of the big orthophoto
   → output a 1280×720 frame of REAL photographic pixels
```

This is roughly 100–150 lines of numpy + OpenCV. It needs no Gazebo, no GPU, and
runs fine on a laptop. The detector stays in its training domain, and every
person's true GPS is known exactly because you placed them.

**Use person crops from the datasets' *test* split, never the train split.**
Otherwise you are showing the model images it memorised.

### The trap that would make the whole measurement worthless

If your renderer projects the ground using the same nadir assumption that
`localize.py` inverts, then localization error is **zero by construction** and
the experiment is circular. It would look like a great result and mean nothing.

**The rule: your renderer uses the aircraft's TRUE roll and pitch from MAVLink.
G2's localizer keeps assuming nadir.**

A real quadcopter banks to move — it is never perfectly nadir. What you then
measure is the genuine cost of the nadir assumption, plus the detector's
bbox-centre error. That is a real, defensible, publishable number.

Agree this with G2 in writing before either of you starts coding.

### The tiers — each one is independently presentable

| | What | Target | Proof it works |
|---|---|---|---|
| **T1** | SITL flying planner waypoints | **12 Sep** | a logged flight track |
| **T2** | Camera renderer + detection on rendered frames | **17 Sep** | detections with known ground truth → **error measured** |
| **T3** | Loop closed — detections update belief in flight, planner re-plans | **22 Sep** | adaptive vs lawnmower, flown |
| **T4** | Live dashboard feed (with G2) | **24 Sep** | dashboard driven by the flight |

> **Hard gate: if T1 is not flying by 14 September, the loop is cut** and you
> move to supporting the deck and video. Say so out loud on the 14th rather than
> spending another week. T1 is a setup problem, and setup problems either
> resolve in days or do not resolve.

### T1 — get something flying (start here)

ArduPilot SITL is a real autopilot compiled to run on your computer. It is what
the flight-controller firmware actually does, not a physics toy.

```bash
# Docker is the reliable path on a Mac — a native build on Apple silicon
# is possible but will cost you a day you do not have.
docker run -it --rm -p 5760:5760 radarku/ardupilot-sitl \
  sim_vehicle.py -v ArduCopter --out=udp:0.0.0.0:14550

# talk to it
pip install pymavlink mavsdk
```

Minimal proof, in Python:

```python
from pymavlink import mavutil
m = mavutil.mavlink_connection('udp:127.0.0.1:14550')
m.wait_heartbeat()
# arm, take off to 20 m, then fly to a lat/lon the planner chose,
# and read position + attitude + battery back every cycle
```

Then wire `simulation/planners.py` to it: the planner already produces a target
**cell**; convert the cell centre to a lat/lon and send it as a waypoint.

**Done when:** the planner picks targets, the aircraft flies to them, and you
have a log of where it actually went. No camera yet.

Keep the grid the same size the simulation already uses — 20×20 cells of 25 m,
**500 × 500 m** — so results are comparable to the 100-seed benchmark.
Battery 1200 s with a 15% return reserve, 5 m/s. All of that is in
`simulation/config.py`; read it, do not retype it.

### T2 — the camera

Build `simulation/camera.py` as described above. Ground sample distance uses the
same formula the rest of the project uses:

```
GSD = 2 · H · tan(FOV/2) / image_width      # 20 m, 60° → 1.80 cm/px
footprint = 23.09 m of ground across the frame
```

Hand G1 ten sample frames the day you have them and ask them to run the
detector. **If recall is far below 0.774, stop and fix the renderer** — that is
a rendering bug, and it is cheap now and expensive after T3 is built on it.

### T3 — close it

Detections → G2's localizer → belief update → planner re-plans mid-flight. Run
the same experiment the grid simulation ran: adaptive vs lawnmower, same world,
same survivors, same detection probability, several seeds.

**Report the result honestly even if it is worse than the grid result.** The
grid simulation assumes a perfect sensor with a fixed 0.824 detection
probability. A real camera at a real bank angle will do worse. That is the
finding — *"here is what the abstraction cost us"* — and it is a better slide
than a number that matches too well.

### If a physical drone appears

The plan does not change. Nobody flies untested autonomy on hardware, so SITL is
the prerequisite either way. Hardware-in-the-loop only starts if T3 lands by
22 September, and even then the flight claim stays limited to what was actually
flown. In India, keep any airframe under 250 g (DGCA nano category) or the
paperwork will outlast the deadline.

---

## Lane B — the video and the deck (Ujjaini)

### The two artefacts are different and only one exists

The **30 September portal submission is an idea PPT, screened online.** No demo,
no questions, no chance to explain. A screener reads slides. That is the
deliverable, and it is not started.

### Video — mostly done, needs finishing (by 8 Sept)

Two shots are already rendered and sitting in `simulation/shots/`:

- `02_good.mp4` — adaptive vs lawnmower with a good prior
- `04_uniform.mp4` — the same with no useful prior, where adaptive's advantage
  correctly shrinks to almost nothing

Add title cards and assemble. `simulation/RENDER_GUIDE.md` has the procedure.

**Include the uniform-prior shot.** It shows the method failing gracefully when
its information is bad, and a judge who sees you volunteer that trusts the rest
of the numbers more. Do not cut it for being less impressive.

Re-cut at the end of the month with T3's flight footage if the loop lands.

### Deck — starts 18 September, not later

Every claim cites a measured number or is labelled as described-only. The
numbers live in `experiments/ARES_MEASURED_NUMBERS.md`. If it is not in that
file, it does not go on a slide.

The scope table goes in the deck as-is, including the honest rows:

| | |
|---|---|
| On-device inference | **Built** — 100% of layers on the Hexagon NPU |
| Alerting / priority scoring | **Built** |
| Command dashboard | **Built** |
| Geo-tagged mapping | **Built** |
| Offline resilience | **Built** |
| RGB + thermal fusion | **Partial** — measured on street-level paired data; no aerial paired dataset exists |
| Hazard classification | **Partial** — 3 classes of 7 |
| Autonomous navigation | **Simulated** on a real flight stack — not flown on hardware |

**Judges reward the honest subset.** This project's strongest asset is that
every number is traceable and every gap is named. Do not let a slide quietly
upgrade a "partial" to a "built".

### One slide nobody owns by training

The team is all CSE. SIH's own guidance rewards a feasibility, impact and
deployment argument — who uses this, what it costs, how it reaches a real
disaster response team. Nobody here has that background, so it has to be
deliberately assigned rather than assumed. Own it.

---

## What not to do

- Do not change the detection JSON contract. It is shared with G1 and G2.
- Do not use rendered/synthetic humans as detector input.
- Do not let the renderer and the localizer share the same attitude assumption.
- Do not claim autonomous flight. Simulated is simulated, and saying so is the
  whole reason the rest of the claims are believed.
- Do not let the loop eat the deck. If T3 slips past 22 September, ship T1+T2
  and write them up — that is already a large upgrade.

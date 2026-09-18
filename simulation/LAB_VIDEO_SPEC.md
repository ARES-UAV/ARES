# Adaptive search — the video

What to build, and the decisions already made for you. The traces exist; this
is the renderer.

---

## 1. Format: a video, not an interactive app

You were right to steer here. An interactive lab asks the judge to click
something and work out what it means. A video makes them watch two drones and
notice, on their own, that one of them keeps missing people.

It also:

- **cannot fail on stage** — same reason the dashboard replays a pre-computed
  `detections.json`
- drops straight into the demo reel, the PPT, and LinkedIn
- needs no laptop, no server, no network

The cost: a judge can't change a parameter. They don't want to. The one axis
worth varying — how good the prior is — is baked into the shots below.

---

## 2. What you already have

`simulation/lab_traces.json` — 1.4 MB, regenerate any time with
`python simulation/export_traces.py`.

```
{
  "meta": { grid_n:20, cell_m:25, battery_s:1200, p_detect:0.824,
            n_survivors:20, speed_ms:5, base:[0,0], ... },
  "runs": [
    { "prior": "good",           // "good" | "mediocre" | "uniform"
      "correlation": 0.645,      // measured against truth — this is what you caption
      "seed": 0,
      "truth":     [[..20x20..]],   // survivors per cell. HIDDEN from the planner
      "prior_map": [[..20x20..]],   // the belief it launched with
      "planners": {
        "lawnmower": { steps, decisions:[], found:10, coverage, find_times, t50 },
        "adaptive":  { steps, decisions, found:20, coverage, find_times, t50 }
      } }, ...
  ]
}
```

**`steps`** — one per cell observed, in order:
`{t: 29.14, y: 5, x: 2, n: 0}` · `n` = people found there · `home:1` on the
return leg.

**`decisions`** — adaptive only, one per target choice:
`{t, from:[y,x], target:[y,x], utility, belief, staleness, cost_s, belief_map}`
where `belief_map` is the full 20×20 at that instant.

Lawnmower has **zero** decisions. That is not missing data — it is the point.

### Three helpers are all you need

```python
def position_at(steps, t):   # last step with step["t"] <= t
def found_at(find_times, t): # count of find_times <= t
def belief_at(decisions, t): # belief_map of the last decision <= t; None for lawnmower
```

Everything on screen comes from those three.

---

## 3. The frame

16:9, 1920×1080. Split screen, one world, one clock.

```
┌──────────────────────────────────────────────────────────────┐
│ ARES · ADAPTIVE SEARCH              GOOD PRIOR · corr +0.65  │
├───────────────────────────┬──────────────────────────────────┤
│ GRID SEARCH               │ ARES ADAPTIVE                    │
│ what search UAVs fly today│ flies where survivors are likely │
│                           │                                  │
│      [ 20 × 20 grid ]     │      [ 20 × 20 grid ]            │
│      plain background     │      belief heatmap background   │
│      survivors, drone,    │      survivors, drone, trail     │
│      trail                │                                  │
│                           │                                  │
├───────────────────────────┼──────────────────────────────────┤
│      FOUND  7 / 20        │      FOUND  18 / 20              │
└──────────────────────────────────────────────────────────────┘
                 T + 08:20   ·   battery 20:00
```

### Five decisions that make it readable without thinking

**1. Survivors are visible from frame one, as faint grey dots.**
Do *not* hide them until found. This is a video, not a puzzle — the judge needs
to see the target set to see one drone missing it. Honesty is preserved because
the *drone* never sees them: the planner only ever read `belief`.

**2. Found survivors flip grey → bright cyan, with a one-second ring pulse.**
The eye tracks colour change with no reading. This is the whole comprehension
mechanism; get it right and the video needs no narration.

**3. The heatmap goes on the adaptive panel ONLY.**
The lawnmower doesn't use belief. Drawing a heatmap under it would imply it
does. Plain grid on the left, glowing map on the right — that asymmetry *is*
the message, and it costs no words.

**4. The counters are enormous.** 100–120 pt. `7` vs `18` is the argument.
Everything else is supporting detail.

**5. One clock, both panels, always in step.**
Same seed, same survivors, same battery, same detection luck. Say so in the
header. If the two panels ever advance at different rates the comparison is
worthless.

### Colours — reuse the ARES palette so it matches the site and dashboard

```
ground        #0B1013     panel         #121A1E
adaptive      #22A7BD     lawnmower     #5A6E76
survivor found#22A7BD     not yet found #3A4A52
battery/alert #FB9A4A     text          #E6EDEF / #A8B8BE
heatmap ramp  #0B1013 → #0E7285 → #22A7BD
```

`#5A6E76` for the lawnmower is not arbitrary — it's the one grey that separates
from the brand cyan by enough for normal and colour-blind vision (16.9 / 14.8
ΔE). The obvious `#6B7F87` fails at 9.8.

---

## 4. Rendering

**matplotlib → PNG frames → ffmpeg.** Not `FuncAnimation` — frames on disk are
far easier to iterate on, and you can re-encode without re-rendering.

```
1200 sim-seconds → 25 video-seconds at 30 fps = 750 frames
so each frame advances 1.6 sim-seconds
```

```bash
ffmpeg -framerate 30 -i frames/good_%04d.png \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart good.mp4
```

`yuv420p` or it won't play in PowerPoint or Safari. `+faststart` for web embeds.

Render one frame first and look at it before generating 750.

---

## 5. The cut — about 60 seconds

| # | Length | Content |
|---|---|---|
| 1 | 4 s | Title card: *"20 minutes of battery. Enough to search half the area. Which half?"* |
| 2 | 25 s | **Good prior**, full run, split screen |
| 3 | 4 s | Freeze on the final frame. Big: **20 / 20 vs 10 / 20** · *3.2× faster to half* |
| 4 | 15 s | **Uniform prior** — *"and if the map is wrong?"* |
| 5 | 4 s | Freeze: **11 vs 4**, still ahead |
| 6 | 6 s | The 100-seed table, and the words **SIMULATION · NOT FLOWN** |

Shot 4 is the one that wins arguments. Anyone can show a demo where their
thing wins. Showing what happens when your central assumption fails, and that
you measured it, reads as engineering rather than salesmanship.

**Shot 6 is not optional.** The scope table says *simulation only, not flown*,
and the video has to agree with it.

---

## 6. Gotchas

**Don't re-implement the planner in JS or anywhere else.** `planners.py` now
has a `recorder` hook, so `export_traces.py` records the *real* algorithm — the
same one the 100-seed benchmark runs. A second implementation drifts the moment
either is edited, and then the video and the deck disagree.

**Don't pick a prettier seed.** The exporter already picks the seed whose
adaptive result is closest to the **median** over 40. If you swap to the best
one, the video stops matching the benchmark.

**The uniform run's numbers move.** On the exported seed it's 11 vs 4; the
100-seed medians are 11 vs 11. Caption the shot with what's on screen, and put
the 100-seed table in shot 6. Don't let a single-seed number get quoted as the
headline.

**Watch the trail length.** A full 1200 s path drawn at once is spaghetti. Fade
it — keep the last ~60 s at full opacity and let older segments drop toward the
background.

**Both drones must start at the same corner.** `meta.base` is `[0,0]`.

---

## 7. Where it goes

| Destination | Form |
|---|---|
| Demo video | the full 60 s as one segment |
| Deck slide 2 | freeze-frame from shot 3 + the headline |
| Website § 06 | replaces or sits beside the chart |
| LinkedIn | the 60 s stands alone |

One rule everywhere: the word **simulation** travels with it.

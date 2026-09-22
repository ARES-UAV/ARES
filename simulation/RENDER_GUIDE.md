# Rendering the video — the procedure

Answers two questions: what "the cut" is, and how you actually get an mp4.

---

## 1. "The cut" — plain meaning

Film jargon. Three words worth knowing:

| word | means |
|---|---|
| **shot** | one continuous piece of footage, no interruption |
| **cut** | the instant one shot ends and the next begins |
| **the cut** | the whole assembled sequence — which shots, what order, how long |

So "the cut" is your **edit**. The table in `LAB_VIDEO_SPEC.md` §5 is a **shot
list**: a plan for six shots totalling ~60 seconds.

**Nobody has made it.** It's a plan, not a file. Nothing has been rendered.

### Who does which part

| | what | who |
|---|---|---|
| Traces | flight data from the real planner | **done** — `lab_traces.json` |
| **Render** | shots 2 and 4 — the split-screen animations → mp4 | **you** |
| Title cards | shots 1, 3, 5, 6 — text on a dark ground | you, or Ujjaini |
| **Assembly** | joining all six into one 60 s file | you *or* Ujjaini |

CONVENTIONS.md gives Ujjaini the demo video. The clean handover: **you render the
two animation shots and hand her the mp4s**, she assembles them with the rest
of the demo reel in her editor. She should not be opening Python.

If you'd rather deliver one finished 60 s clip she can drop in whole, §5 below
does the assembly in ffmpeg with no editor at all.

---

## 2. Rendering — six steps

### Step 1 · dependencies

```bash
source .venv/bin/activate
pip install matplotlib          # numpy is already there
ffmpeg -version                 # brew install ffmpeg if missing
```

### Step 2 · the three lookups

Everything on screen comes from these. `steps` is time-ordered, so a linear
scan with a cursor is enough — don't re-scan from the start each frame or 750
frames will crawl.

```python
import json, bisect
TR = json.load(open("simulation/lab_traces.json"))

def position_at(steps, t, cursor=0):
    """Last step at or before t. Returns (y, x, cursor)."""
    while cursor + 1 < len(steps) and steps[cursor + 1]["t"] <= t:
        cursor += 1
    s = steps[cursor]
    return s["y"], s["x"], cursor

def found_at(find_times, t):
    """How many survivors found by t. find_times is sorted."""
    return bisect.bisect_right(find_times, t)

def belief_at(decisions, t):
    """The 20x20 belief map at t, or None for the lawnmower."""
    if not decisions:
        return None                      # lawnmower has no decisions. Correct.
    i = bisect.bisect_right([d["t"] for d in decisions], t) - 1
    return decisions[max(i, 0)]["belief_map"]
```

### Step 3 · which survivors are lit

A survivor turns cyan when the drone finds it. `find_times` gives you *when*
but not *which cell* — take that from the steps, where `n > 0`:

```python
def found_cells_by(steps, t):
    """{(y,x): earliest_find_time} for cells with a find at or before t."""
    out = {}
    for s in steps:
        if s["t"] > t:
            break
        if s["n"] > 0 and (s["y"], s["x"]) not in out:
            out[(s["y"], s["x"])] = s["t"]
    return out
```

Then a cell in `truth` renders faint grey if it isn't in that dict, bright cyan
if it is, and gets a ring pulse while `t - found_time < 1.0`.

### Step 4 · one frame, and look at it

**Render frame 400 first.** Not frame 0 — nothing has happened at frame 0.
Around 400 the adaptive drone is deep in a cluster and the lawnmower is still
ploughing. Save it as a PNG and open it.

Iterate on that single frame until it reads at a glance from two metres away.
Only then render all 750. Getting this backwards costs an hour per mistake.

The layout, palette and the five readability decisions are in
`LAB_VIDEO_SPEC.md` §3.

### Step 5 · timing

```
flight runs to about 1240 s   (a little past the 1200 s battery — the return
                               leg keeps flying after turn-back)
target 25 video-seconds at 30 fps  =  750 frames
so   sim_t = frame * (1240 / 750)  ≈  1.65 s per frame
```

Use the same `sim_t` for **both** panels in a frame. That shared clock is what
makes the comparison mean anything.

### Step 6 · frames to mp4

```bash
ffmpeg -y -framerate 30 -i frames/good_%04d.png \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart \
  shots/02_good.mp4
```

- `yuv420p` — without it, PowerPoint and Safari refuse to play the file
- `crf 18` — visually lossless; 23 is default, lower is bigger
- `+faststart` — index at the front, so web embeds start instantly

---

## 3. What to render

Two animation shots:

| shot | run | length | frames |
|---|---|---|---|
| 02 | `prior == "good"` | 25 s | 750 |
| 04 | `prior == "uniform"` | 15 s | 450 |

For shot 04 at 450 frames, `sim_t = frame * (1240 / 450)` ≈ 2.76 s per frame.
Faster, which is right — it's the supporting shot.

---

## 4. Title cards

Easiest path: render them in matplotlib with the same fonts and palette, one
PNG each. Consistent with the animation for free.

| shot | text |
|---|---|
| 01 | *20 minutes of battery.* / *Enough to search half the area.* / **Which half?** |
| 03 | **20 / 20** vs **10 / 20** · reached half the survivors **4.7× faster** |
| 05 | **11** vs **4** · *the grid never reached half at all* |
| 06 | the 100-seed table + **SIMULATION · NOT FLOWN** |

Shot 03's numbers come from the good-prior seed: adaptive t50 220 s, lawnmower
1035 s. Shot 05: on the uniform seed the lawnmower's `t50` is **null** — it
never found ten of the twenty. That is a real and very quotable result.

**Caption these as the seed's numbers, not as the headline.** The 100-seed
medians are **3.11× / 2.10× / 1.27×**, and those belong on shot 06.

> **Shot 03 and 05's figures are stale.** They come from an export made before
> commit `828877b`, which changed the lawnmower's timing — see RESULTS.md §4.
> Re-run `export_traces.py` and read the new seed's numbers off it before
> burning either caption into the video. Do not carry 4.7× over on trust.

A still becomes a video segment like this:

```bash
ffmpeg -y -loop 1 -i cards/01_title.png -t 4 \
  -c:v libx264 -pix_fmt yuv420p -r 30 -crf 18 shots/01_title.mp4
```

---

## 5. Assembly — the cut itself

Only if you're delivering the finished 60 s rather than handing shots to
Ujjaini.

```bash
cat > shots/order.txt <<'EOF'
file '01_title.mp4'
file '02_good.mp4'
file '03_result.mp4'
file '04_uniform.mp4'
file '05_result.mp4'
file '06_table.mp4'
EOF

ffmpeg -y -f concat -safe 0 -i shots/order.txt -c copy adaptive_search.mp4
```

`-c copy` joins without re-encoding — instant, and no quality loss. It only
works if every segment shares codec, resolution and frame rate, which is why
all six are rendered 1920×1080 at 30 fps h264.

If concat complains, re-encode instead:

```bash
ffmpeg -y -f concat -safe 0 -i shots/order.txt \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart adaptive_search.mp4
```

### Freeze on the last frame instead of a title card

Sometimes stronger than a card — the final state stays on screen while the
numbers appear over it:

```bash
ffmpeg -y -sseof -0.1 -i shots/02_good.mp4 -vframes 1 cards/02_last.png
```

Then loop that PNG for 4 s as in §4, optionally with the numbers drawn on top.

---

## 6. Iterate fast

```bash
# one frame, mid-flight
python simulation/render_video.py --run good --frame 400 --out /tmp/f.png

# a 3-second sample before committing to 750 frames
python simulation/render_video.py --run good --frames 90 --fps 30
```

Build those two flags in first. The difference between a good render and a bad
one is how many times you looked at a frame, and that's a function of how fast
the loop is.

---

## 7. Two things that will bite

**Don't re-scan `steps` from index 0 every frame.** 750 frames × 246 steps is
fine, but the same mistake on `found_cells_by` — which walks the whole list —
gets slow once you add the ring pulse. Cache it.

**The lawnmower has no belief map.** `belief_at` returns `None` and that is
correct, not a missing case to fill in. Draw a plain grid. If you shade it, you
are showing a drone using information it never had.

#!/usr/bin/env python3
"""
Render the adaptive-search video frames.

    python simulation/render_video.py --run good --frame 400 --out /tmp/f.png
    python simulation/render_video.py --run good --frames 90
    python simulation/render_video.py --run good --frames 750
    python simulation/render_video.py --run uniform --frames 450

Look at ONE frame before rendering 750. Frame 400 is a good one — the adaptive
drone is working a cluster and the lawnmower is still ploughing rows. Frame 0
shows nothing happening.

Then, to make the mp4:

    ffmpeg -y -framerate 30 -i simulation/frames/good_%04d.png \\
      -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart \\
      simulation/shots/02_good.mp4

WHAT THIS DRAWS, AND WHY

    Survivors are visible from the first frame, faint. This is a video, not a
    puzzle — a viewer has to see the target set to notice one drone missing it.
    It stays honest because the PLANNER never saw them: it only ever read
    `belief`, and `truth` is used here for drawing and nowhere else.

    The heatmap is drawn on the ADAPTIVE panel only. The lawnmower does not use
    belief, so shading its grid would show a drone using information it never
    had. `belief_at` returns None for it, and that is the correct answer, not a
    gap to fill.

    Both panels advance on ONE clock. Same seed, same survivors, same detection
    coin-flips — the only difference is where each chose to fly.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Circle, Rectangle

HERE = Path(__file__).resolve().parent
TRACES = HERE / "lab_traces.json"
FRAMES = HERE / "frames"

# ── palette · frontend/src/tokens.css ─────────────────────────────────
GROUND, PANEL, LINE = "#0B1013", "#121A1E", "#22323A"
INK, INK_SOFT, DIM = "#E6EDEF", "#A8B8BE", "#6B7F87"
CY = "#22A7BD"      # adaptive, and a found survivor
LAWN = "#5A6E76"      # the baseline. NOT --dim: that fails colour separation
AMBER = "#FB9A4A"      # battery
SURV = "#3A4A52"      # a survivor nobody has found yet

HEAT = LinearSegmentedColormap.from_list("ares", [GROUND, "#0E3B46", "#0E7285", CY])

TRAIL_S = 90.0        # seconds of path drawn at full strength
PULSE_S = 1.2         # how long a find flashes its ring


# ══════════════════════════════════════════════════════════════════════
#  Reading the traces
# ══════════════════════════════════════════════════════════════════════

def load() -> dict:
    if not TRACES.is_file():
        sys.exit(f"{TRACES} not found. Run: python simulation/export_traces.py")
    return json.loads(TRACES.read_text())


def position_at(steps: list, t: float) -> tuple[int, int]:
    """Where the drone is at t — the last step at or before it."""
    i = bisect.bisect_right([s["t"] for s in steps], t) - 1
    s = steps[max(i, 0)]
    return s["y"], s["x"]


def path_until(steps: list, t: float) -> list[tuple[float, int, int]]:
    """(t, y, x) for every cell flown at or before t."""
    out = []
    for s in steps:
        if s["t"] > t:
            break
        out.append((s["t"], s["y"], s["x"]))
    return out


def found_at(find_times: list, t: float) -> int:
    return bisect.bisect_right(find_times, t)


def found_cells_by(steps: list, t: float) -> dict:
    """{(y, x): first time a find happened there} at or before t."""
    out = {}
    for s in steps:
        if s["t"] > t:
            break
        if s["n"] > 0:
            out.setdefault((s["y"], s["x"]), s["t"])
    return out


def belief_at(decisions: list, t: float):
    """The belief map at t. None for the lawnmower — it has no decisions."""
    if not decisions:
        return None
    i = bisect.bisect_right([d["t"] for d in decisions], t) - 1
    return np.array(decisions[max(i, 0)]["belief_map"])


# ══════════════════════════════════════════════════════════════════════
#  Drawing
# ══════════════════════════════════════════════════════════════════════

def draw_panel(ax, run, planner, t, n, title, subtitle, colour, show_heat):
    pl = run["planners"][planner]
    truth = np.array(run["truth"])

    ax.set_facecolor(PANEL)
    ax.set_xlim(0, n); ax.set_ylim(n, 0)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
    for sp in ax.spines.values():
        sp.set_color(LINE); sp.set_linewidth(1.5)

    # Belief heatmap — adaptive only.
    if show_heat:
        bel = belief_at(pl["decisions"], t)
        if bel is not None:
            ax.imshow(bel, cmap=HEAT, vmin=0, vmax=1, extent=[0, n, n, 0],
                      interpolation="bilinear", zorder=1, alpha=0.95)

    # Cell grid, faint.
    for k in range(n + 1):
        ax.plot([k, k], [0, n], color=LINE, lw=0.4, alpha=0.5, zorder=2)
        ax.plot([0, n], [k, k], color=LINE, lw=0.4, alpha=0.5, zorder=2)

    # Survivors. Faint until found, then the panel's colour + a ring pulse.
    found = found_cells_by(pl["steps"], t)
    for (y, x), count in np.ndenumerate(truth):
        if not count:
            continue
        cx, cy = x + 0.5, y + 0.5
        hit = found.get((y, x))
        ax.scatter([cx], [cy], s=110 if hit else 70,
                   c=colour if hit else SURV,
                   edgecolors=GROUND, linewidths=1.2, zorder=6)
        if hit is not None and 0 <= t - hit < PULSE_S:
            frac = (t - hit) / PULSE_S
            ax.add_patch(Circle((cx, cy), 0.5 + frac * 2.2, fill=False,
                                edgecolor=colour, lw=2.5 * (1 - frac), zorder=7))

    # Trail — recent path bright, older path fading into the panel.
    pts = path_until(pl["steps"], t)
    if len(pts) > 1:
        for (t0, y0, x0), (t1, y1, x1) in zip(pts, pts[1:]):
            age = t - t1
            a = 0.85 if age < TRAIL_S else max(0.06, 0.85 * (1 - (age - TRAIL_S) / 600))
            ax.plot([x0 + .5, x1 + .5], [y0 + .5, y1 + .5],
                    color=colour, lw=1.6, alpha=a, solid_capstyle="round", zorder=4)

    # The drone.
    dy, dx = position_at(pl["steps"], t)
    ax.add_patch(Circle((dx + .5, dy + .5), 0.62, facecolor=colour,
                        edgecolor=GROUND, lw=1.6, zorder=8))
    ax.add_patch(Circle((dx + .5, dy + .5), 1.5, fill=False,
                        edgecolor=colour, lw=1.1, alpha=0.35, zorder=8))

    # Title and subtitle both above the grid. The subtitle was under it and
    # fell outside the axes box, which clips.
    ax.set_title(f"{title}\n", color=INK, fontsize=17, fontweight="bold",
                 loc="left", pad=26)
    ax.text(0, 1.012, subtitle, color=DIM, fontsize=11,
            transform=ax.transAxes, va="bottom", ha="left")
    return found_at(pl["find_times"], t)


def render(run: dict, meta: dict, t: float, out: Path) -> None:
    n = meta["grid_n"]
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=GROUND)

    mins, secs = divmod(int(t), 60)
    bmin, bsec = divmod(int(meta["battery_s"]), 60)

    fig.text(0.035, 0.945, "ARES  ·  ADAPTIVE SEARCH", color=INK,
             fontsize=21, fontweight="bold")
    fig.text(0.035, 0.915,
             "same survivors  ·  same battery  ·  same detection luck  ·  "
             "only the choice of where to fly differs",
             color=DIM, fontsize=11)

    # The clock lives up here, not between the counters — the gap between the
    # panels is 7% of the width and a 25pt readout does not fit in it.
    fig.text(0.5, 0.947, f"T + {mins:02d}:{secs:02d}", color=INK,
             fontsize=26, fontweight="bold", ha="center", va="center")
    fig.text(0.5, 0.918, f"of {bmin:02d}:{bsec:02d} battery",
             color=AMBER if t > meta["battery_s"] * 0.85 else DIM,
             fontsize=11, ha="center", va="center")

    fig.text(0.965, 0.945,
             f"{run['prior'].upper()} PRIOR  ·  correlation {run['correlation']:+.2f}",
             color=CY, fontsize=15, fontweight="bold", ha="right", va="center")

    axL = fig.add_axes([0.055, 0.200, 0.40, 0.605])
    axR = fig.add_axes([0.545, 0.200, 0.40, 0.605])

    fl = draw_panel(axL, run, "lawnmower", t, n,
                    "GRID SEARCH", "what search UAVs fly today", LAWN, False)
    fa = draw_panel(axR, run, "adaptive", t, n,
                    "ARES ADAPTIVE", "flies where survivors are likely", CY, True)

    # Counters. The number and its label are separate texts at FIXED
    # positions — an offset measured from the digits would move as the count
    # goes from 1 to 2 digits, which is exactly when someone is reading it.
    total = meta["n_survivors"]
    for x0, val, colour in ((0.086, fl, LAWN), (0.576, fa, CY)):
        fig.text(x0, 0.080, f"{val}", color=colour, fontsize=80,
                 fontweight="bold", va="bottom", ha="left")
        fig.text(x0, 0.042, f"OF {total} SURVIVORS FOUND", color=DIM,
                 fontsize=12.5, va="bottom", ha="left")

    # Battery bar, full width under the panels rather than squeezed between.
    bar_w = 0.89 * min(t / meta["battery_s"], 1.0)
    fig.patches.append(Rectangle((0.055, 0.022), 0.89, 0.005,
                                 facecolor=LINE, transform=fig.transFigure,
                                 zorder=3))
    fig.patches.append(Rectangle((0.055, 0.022), bar_w, 0.005,
                                 facecolor=AMBER, transform=fig.transFigure,
                                 zorder=4))

    fig.text(0.955, 0.045, "SIMULATION  ·  NOT FLOWN", color=DIM,
             fontsize=11.5, ha="right", va="bottom", fontweight="bold")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=GROUND)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="good", choices=["good", "mediocre", "uniform"])
    ap.add_argument("--frame", type=int, help="render this ONE frame and stop")
    ap.add_argument("--frames", type=int, default=750, help="total frames (default 750)")
    ap.add_argument("--out", type=Path, help="output path for a single frame")
    args = ap.parse_args()

    data = load()
    run = next(r for r in data["runs"] if r["prior"] == args.run)
    meta = data["meta"]

    # The flight runs a little past the battery — the return leg keeps flying.
    end = max(pl["steps"][-1]["t"] for pl in run["planners"].values())
    per_frame = end / args.frames

    if args.frame is not None:
        out = args.out or FRAMES / f"{args.run}_preview.png"
        t = args.frame * per_frame
        render(run, meta, t, out)
        print(f"frame {args.frame}  t = {t:.1f}s  →  {out}")
        return

    outdir = FRAMES
    outdir.mkdir(parents=True, exist_ok=True)
    for i in range(args.frames):
        render(run, meta, i * per_frame, outdir / f"{args.run}_{i:04d}.png")
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{args.frames}", flush=True)

    print(f"\n{args.frames} frames in {outdir}\n\nNow:\n"
          f"  ffmpeg -y -framerate 30 -i {outdir}/{args.run}_%04d.png \\\n"
          f"    -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart \\\n"
          f"    simulation/shots/{args.run}.mp4")


if __name__ == "__main__":
    main()

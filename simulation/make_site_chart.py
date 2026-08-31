"""
Render the adaptive-search result as a dark chart for the public site.

    python simulation/make_site_chart.py

WHY THIS EXISTS AND WHAT IT IS NOT
    `run.py` writes results/found_vs_time.png on a white ground — the figure for
    a document. docs/index.html is committed dark, and a white rectangle on it
    reads as a hole in the page.

    So this renders THE SAME DATA in the site palette. It does not re-run the
    experiment and it cannot: it only reads results/results.json, which run.py
    wrote. There is one source of numbers and two renderings of it.

COLOURS ARE NOT A TASTE DECISION HERE
    Palette lifted from frontend/src/tokens.css. The two series were checked for
    separation on the #070B0D ground rather than eyeballed:

        adaptive   #22A7BD   the brand cyan — the subject
        lawnmower  #5A6E76   recessive, and DARKER than the subject so the
                             baseline stays visually behind it

    The obvious choice, --dim #6B7F87, fails: against the cyan it separates by
    only 9.8 ΔE for normal vision and 6.2 for deuteranopia. Someone would have
    to read the legend to tell two lines apart. #5A6E76 gives 16.9 / 14.8 and
    still holds 3:1 against the background.

    Colour is not carrying identity alone regardless: the baseline is dashed,
    the subject is solid and heavier, and both are labelled on the first panel.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results" / "results.json"
OUT = HERE.parent / "docs" / "img" / "adaptive-search.png"

# ── palette · frontend/src/tokens.css ──────────────────────────────────
VOID = "#070B0D"      # --void      page ground; the figure sits flush on it
INK = "#E6EDEF"      # --ink       panel titles
DIM = "#6B7F87"      # --dim       axis text
LINE = "#162228"      # --line-soft grid
CY = "#22A7BD"      # --cy        adaptive
BASE = "#5A6E76"      # baseline    lawnmower — see docstring
AM = "#FB9A4A"      # --p2        battery cutoff

BATTERY_S = 1200.0
N_SURVIVORS = 20

plt.rcParams.update({
    "font.family": "monospace",
    "font.monospace": ["DejaVu Sans Mono"],
    "figure.facecolor": VOID,
    "axes.facecolor": VOID,
    "savefig.facecolor": VOID,
})


def curve(find_times: list[list[float]], grid: np.ndarray) -> np.ndarray:
    """Median survivors-found-by-time t, across seeds.

    Built per-seed and then medianed — NOT median(t50), median(t80),
    median(t100), which is over a different subset of seeds at each point and
    plots a line that travels backwards. run.py carries the full explanation.
    """
    per_seed = np.array(
        [[np.searchsorted(ft, t, side="right") for t in grid] for ft in find_times],
        dtype=float,
    )
    return np.median(per_seed, axis=0)


def med(xs) -> float:
    xs = np.asarray(xs, dtype=float)
    return float("nan") if np.all(np.isnan(xs)) else float(np.nanmedian(xs))


def main() -> None:
    results = json.loads(RESULTS.read_text())
    grid = np.linspace(0, BATTERY_S, 300)

    fig, axes = plt.subplots(1, len(results), figsize=(13.6, 4.35), sharey=True)
    axes = np.atleast_1d(axes)

    for i, (ax, res) in enumerate(zip(axes, results)):
        for name, colour, dash, lw in (
            ("lawnmower", BASE, (5, 3), 2.0),
            ("adaptive", CY, None, 2.8),
        ):
            y = curve(res["planners"][name]["find_times"], grid)
            ax.plot(grid, y, color=colour, lw=lw,
                    dashes=dash if dash else (None, None),
                    solid_capstyle="round",
                    zorder=3 if name == "adaptive" else 2,
                    label=name.upper())

        # Battery cutoff. Label sits left of the line, low, where neither
        # curve reaches in any of the three panels.
        ax.axvline(BATTERY_S, color=AM, ls=(0, (2, 4)), lw=1.3, zorder=1)
        ax.text(BATTERY_S - 22, 0.5, "BATTERY", color=AM, fontsize=7.5,
                rotation=90, va="bottom", ha="right")

        # The headline, on the panel it belongs to.
        a, l = med(res["planners"]["adaptive"]["t50"]), med(res["planners"]["lawnmower"]["t50"])
        ax.text(0.035, 0.955, f"{l / a:.1f}× FASTER TO HALF",
                transform=ax.transAxes, fontsize=9.5, fontweight="bold",
                color=CY, va="top")

        ax.set_title(f"{res['prior'].upper()}  ·  PRIOR CORR {res['correlation']:+.2f}",
                     fontsize=10, fontweight="bold", color=INK, pad=13)
        ax.grid(True, color=LINE, lw=1, alpha=1)
        ax.set_axisbelow(True)
        ax.set_ylim(0, N_SURVIVORS + 1.6)
        ax.set_xlim(-30, BATTERY_S + 60)
        ax.set_yticks(range(0, N_SURVIVORS + 1, 5))   # people are whole numbers
        ax.set_xticks(range(0, 1201, 300))
        ax.tick_params(colors=DIM, labelsize=8, length=0)
        for side, on in (("left", True), ("bottom", True), ("top", False), ("right", False)):
            ax.spines[side].set_visible(on)
            if on:
                ax.spines[side].set_color(LINE)

    axes[0].set_ylabel(f"SURVIVORS FOUND (OF {N_SURVIVORS})", fontsize=8,
                       color=DIM, labelpad=9)
    fig.supxlabel("SECONDS INTO THE FLIGHT", fontsize=8, color=DIM, y=-0.02)

    fig.suptitle(
        f"ADAPTIVE SEARCH vs LAWNMOWER  ·  MEDIAN OF {results[0]['n_seeds']} SEEDS  "
        f"·  P(DETECT) = 0.824, MEASURED",
        fontsize=10.5, fontweight="bold", color=INK, y=1.075)

    # Legend lives at figure level, under the title. Inside a panel it collided
    # with the battery marker in every position that was otherwise clear.
    handles, labels = axes[0].get_legend_handles_labels()
    order = [labels.index("ADAPTIVE"), labels.index("LAWNMOWER")]
    leg = fig.legend([handles[i] for i in order], [labels[i] for i in order],
                     frameon=False, fontsize=8.5, ncol=2, loc="upper center",
                     bbox_to_anchor=(0.5, 1.035), handlelength=2.6,
                     columnspacing=2.6)
    for t in leg.get_texts():
        t.set_color(DIM)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170, bbox_inches="tight", facecolor=VOID)
    plt.close(fig)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

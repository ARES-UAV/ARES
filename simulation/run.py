"""
The experiment runner.

    python simulation/run.py                 # all three priors, 30 seeds
    python simulation/run.py --prior uniform # just the hard case
    python simulation/run.py --seeds 5       # quick check

WHAT IT DOES
    For every prior quality, and every seed, it builds one world and flies BOTH
    planners over it. Same survivors, same detection luck, same battery — only
    the choice of where to fly next differs. Then it writes a results table and
    a plot.

WHY BOTH PLANNERS SEE AN IDENTICAL WORLD
    If each planner got its own random layout, a gap between them might just be
    the gap between two random maps. Re-seeding numpy before each flight makes
    the detection coin-flips identical too, so the ONLY thing that varies is the
    strategy.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

import numpy as np

import config as C
import world as W
from planners import PLANNERS


def run_one(prior_name: str, w_value: float, n_seeds: int) -> dict:
    """Fly both planners over `n_seeds` identical worlds. Returns raw results."""
    out = {p: {"found": [], "coverage": [], "t50": [], "t80": [], "t100": [],
               "path_m": [], "home": [], "find_times": []} for p in PLANNERS}
    correlations = []

    for seed in range(n_seeds):
        _, corr = W.build(seed, w_value)
        correlations.append(corr)

        for pname, fn in PLANNERS.items():
            world, _ = W.build(seed, w_value)
            np.random.seed(seed)               # identical detection luck
            f = fn(world)

            r = out[pname]
            r["found"].append(f.found)
            r["coverage"].append(f.coverage)
            r["path_m"].append(f.path_m)
            r["home"].append(f.returned_home)
            r["find_times"].append(sorted(f.find_times))
            for key, frac in (("t50", 0.5), ("t80", 0.8), ("t100", 1.0)):
                t = f.time_to_find(frac)
                r[key].append(np.nan if t is None else t)

    return {"prior": prior_name, "w": w_value,
            "correlation": float(np.median(correlations)),
            "planners": out, "n_seeds": n_seeds}


def _med(xs) -> float:
    """Median that tolerates all-NaN (a target never reached in any run)."""
    xs = np.asarray(xs, dtype=float)
    return float("nan") if np.all(np.isnan(xs)) else float(np.nanmedian(xs))


def table(results: list[dict]) -> str:
    """Markdown results table — medians, with how often each target was hit."""
    L = ["| Prior | Corr. | Planner | Found /20 | Coverage | t50 | t80 | Reached 80% |",
         "|---|---:|---|---:|---:|---:|---:|---:|"]
    for res in results:
        for p in PLANNERS:
            r = res["planners"][p]
            t80 = _med(r["t80"])
            hit80 = int(np.sum(~np.isnan(np.asarray(r["t80"], dtype=float))))
            L.append(
                f"| {res['prior']} | {res['correlation']:.2f} | {p} | "
                f"{_med(r['found']):.1f} | {100*_med(r['coverage']):.0f}% | "
                f"{_med(r['t50']):.0f} s | "
                f"{'—' if np.isnan(t80) else f'{t80:.0f} s'} | "
                f"{hit80}/{res['n_seeds']} |")
    return "\n".join(L)


def plot(results: list[dict], path) -> None:
    """Survivors found against time — one panel per prior quality."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CY, AM, DIM, LINE = "#0E7A8F", "#A85A0C", "#7A8C93", "#CBD8DC"
    fig, axes = plt.subplots(1, len(results), figsize=(4.6 * len(results), 4.1),
                             sharey=True)
    axes = np.atleast_1d(axes)

    for ax, res in zip(axes, results):
        # HOW THIS CURVE IS BUILT, AND THE MISTAKE IT AVOIDS
        #   The obvious way — median(t50), median(t80), median(t100) — is
        #   WRONG. Each of those medians is taken over a different subset of
        #   seeds, because not every run reaches 80% or 100%. The median t100
        #   (over only the runs that got there, which are the lucky fast ones)
        #   can land EARLIER than the median t80 taken over many more runs, and
        #   the plotted line then travels backwards in time.
        #
        #   The correct construction: for each seed count how many were found
        #   by time t, then take the median of those counts across seeds at
        #   every t. Monotonic by construction, and it uses every run.
        grid = np.linspace(0, C.BATTERY_S, 300)
        for pname, colour in (("lawnmower", DIM), ("adaptive", CY)):
            r = res["planners"][pname]
            per_seed = np.array([
                [np.searchsorted(ft, t, side="right") for t in grid]
                for ft in r["find_times"]
            ], dtype=float)
            ax.plot(grid, np.median(per_seed, axis=0), color=colour, lw=2.4,
                    label=pname, zorder=3 if pname == "adaptive" else 2)

        ax.axvline(C.BATTERY_S, color=AM, ls="--", lw=1.4, zorder=1)
        ax.text(C.BATTERY_S, 1, " battery", color=AM, fontsize=8, rotation=90,
                va="bottom", ha="right")
        ax.set_title(f"{res['prior']}  ·  prior corr {res['correlation']:.2f}",
                     fontsize=11, fontweight="bold")
        ax.set_xlabel("seconds")
        ax.grid(alpha=.25, color=LINE)
        ax.set_ylim(0, C.N_SURVIVORS + 1)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    axes[0].set_ylabel(f"survivors found (of {C.N_SURVIVORS})")
    axes[0].legend(frameon=False, fontsize=9)
    fig.suptitle("Adaptive search vs lawnmower — median of "
                 f"{results[0]['n_seeds']} seeds, P(detect) = {C.P_DETECT} measured",
                 fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Adaptive search experiment")
    ap.add_argument("--prior", default="all",
                    choices=["all", *C.PRIOR_NOISE_LEVELS])
    ap.add_argument("--seeds", type=int, default=C.N_SEEDS)
    args = ap.parse_args()

    names = list(C.PRIOR_NOISE_LEVELS) if args.prior == "all" else [args.prior]
    results = [run_one(n, C.PRIOR_NOISE_LEVELS[n], args.seeds) for n in names]

    C.RESULTS_DIR.mkdir(exist_ok=True)
    (C.RESULTS_DIR / "results.json").write_text(json.dumps(results, indent=2))
    (C.RESULTS_DIR / "results.md").write_text(
        "# Adaptive search — results\n\n"
        f"Generated by `simulation/run.py --seeds {args.seeds}`. "
        "Medians across seeds. Both planners fly identical worlds.\n\n"
        + table(results)
        + "\n\n**P(detect) = 0.824 is measured** — our recall at conf 0.18, 960 px, "
          "on 86,092 instances. Everything else is simulated. This tests the "
          "planner, not the detector, and there is no aircraft.\n")
    plot(results, C.RESULTS_DIR / "found_vs_time.png")

    print(table(results))
    print(f"\nwrote {C.RESULTS_DIR}/results.md, results.json, found_vs_time.png")

    for res in results:
        a = _med(res["planners"]["adaptive"]["t50"])
        l = _med(res["planners"]["lawnmower"]["t50"])
        if a and not np.isnan(a) and not np.isnan(l):
            print(f"  {res['prior']:<9} adaptive reaches 50% {l/a:.2f}x faster")


if __name__ == "__main__":
    main()

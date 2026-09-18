#!/usr/bin/env python3
"""
Is the lawnmower baseline actually information-blind?

    python simulation/check_baseline.py

WHAT PROMPTED THIS
    In the rendered video the grid drone leaves its rows near the end and
    wanders diagonally. That is `go_home()`, and it picks each next cell by
    the HIGHEST BELIEF among neighbours that close the distance to base.

    For the adaptive planner that is correct — it uses belief everywhere.
    For the lawnmower it is not: the whole point of the baseline is a fixed
    pattern that cannot use information, and its return leg was using it.

    The error runs in the conservative direction — a belief-guided return
    makes the baseline STRONGER, so adaptive's measured advantage is a lower
    bound rather than an inflated one. But "the lawnmower cannot use
    information" is a sentence in the write-up, and it was not true.

WHAT THIS MEASURES
    The same 100 seeds, lawnmower only, both ways:

      belief-guided return   what the benchmark has been running
      blind return           straight-ish walk to base, belief ignored

    If the difference is negligible, fix it for honesty and the numbers barely
    move. If it is large, the published comparison needs restating.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import config as C          # noqa: E402
import planners as P        # noqa: E402
import world as W           # noqa: E402

N_SEEDS = 100


def blind_go_home(self) -> None:
    """Return to base ignoring belief — the honest baseline behaviour.

    Same movement rule minus the one line that reads the belief map: step to
    whichever neighbour closes the most distance, ties broken by index so the
    walk is deterministic. Still observes what it passes over, because the
    camera does not switch off — it just stops CHOOSING by what it hopes to
    find.
    """
    guard = 0
    while self.pos != C.BASE_CELL and guard < C.GRID_N * 4:
        guard += 1
        here_d = P.metres(self.pos, C.BASE_CELL)
        best, best_d = None, here_d
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = self.pos[0] + dy, self.pos[1] + dx
                if not (0 <= ny < C.GRID_N and 0 <= nx < C.GRID_N):
                    continue
                d = P.metres((ny, nx), C.BASE_CELL)
                if d < best_d:
                    best, best_d = (ny, nx), d
        if best is None:
            break
        self.t += P.travel_time(self.pos, best)
        self.flight.path_m += P.metres(self.pos, best)
        self.pos = best
        self.flight.path.append(best)
        self.w.observe(best[0], best[1], self.t)
    self.flight.returned_home = (self.pos == C.BASE_CELL)


def run(blind: bool, w_value: float) -> dict:
    original = P.Drone.go_home
    if blind:
        P.Drone.go_home = blind_go_home
    try:
        found, cov, t50 = [], [], []
        for seed in range(N_SEEDS):
            world, _ = W.build(seed, w_value)
            np.random.seed(seed)
            f = P.run_lawnmower(world)
            found.append(f.found)
            cov.append(f.coverage)
            t = f.time_to_find(0.5)
            t50.append(np.nan if t is None else t)
        return {
            "found": float(np.median(found)),
            "coverage": float(np.median(cov)),
            "t50": float(np.nanmedian(t50)) if not np.all(np.isnan(t50)) else float("nan"),
            "reached50": int(np.sum(~np.isnan(t50))),
        }
    finally:
        P.Drone.go_home = original


def main() -> None:
    print(f"Lawnmower baseline, {N_SEEDS} seeds, median\n")
    print(f"{'prior':<10}{'return leg':<16}{'found':>7}{'coverage':>10}"
          f"{'t50':>9}{'reached 50%':>13}")
    print("-" * 66)

    for name, w_value in C.PRIOR_NOISE_LEVELS.items():
        rows = []
        for blind, label in ((False, "belief-guided"), (True, "blind")):
            r = run(blind, w_value)
            rows.append(r)
            t50 = "—" if np.isnan(r["t50"]) else f"{r['t50']:.0f} s"
            print(f"{name:<10}{label:<16}{r['found']:>7.1f}"
                  f"{100*r['coverage']:>9.0f}%{t50:>9}"
                  f"{r['reached50']:>10}/{N_SEEDS}")
        d = rows[1]["found"] - rows[0]["found"]
        print(f"{'':<26}{'Δ found ' + f'{d:+.1f}':>16}\n")

    print("A negative Δ means the belief-guided return was flattering the")
    print("baseline, and the honest version makes adaptive look BETTER.")


if __name__ == "__main__":
    main()

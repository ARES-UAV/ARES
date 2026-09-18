#!/usr/bin/env python3
"""
"You found them early — but do you ever find the rest?"

    python simulation/multi_sortie.py

THE QUESTION, WHICH IS THE RIGHT ONE TO ASK
    Adaptive finds 20 of 20 with a good prior and covers 33% of the area. The
    lawnmower finds 11 and covers 56%. The obvious objection:

        "The grid pattern is systematic. Fly it long enough and it finds
         everyone. Yours goes where it guesses — do the ones it skipped ever
         get searched, or are they abandoned?"

    A single 20-minute sortie cannot answer that, because neither aircraft
    finishes the area in one battery. So fly several, back to back, and see.

HOW EACH PLANNER CONTINUES
    lawnmower  resumes its pattern where the last sortie ran out. That is what
               an operator flying a grid actually does, and it is the strongest
               fair version of the baseline.

    adaptive   keeps its belief map. Cells it searched have low belief and a
               recent `last_seen`; cells it skipped have been accumulating
               STALENESS the whole time. That term exists precisely so an
               ignored cell eventually outranks a mildly interesting one — the
               coverage guarantee, tested here rather than asserted.

    Both start each sortie at base with a full battery. The world persists:
    survivors already found stay found.

WHAT WOULD FALSIFY THE DESIGN
    If adaptive's coverage flatlines across sorties while the lawnmower's
    climbs, the staleness term does not work and "priority changes the order,
    not the coverage" is false. That is the result this is looking for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import config as C          # noqa: E402
import planners as P        # noqa: E402
import world as W           # noqa: E402

N_SEEDS = 60
N_SORTIES = 4
OUT = HERE / "results" / "multi_sortie.json"


def fly_lawnmower(world, start_index: int, t0: float):
    """One sortie of the fixed pattern, resuming at `start_index`."""
    d = P.Drone(world, "lawnmower")
    d.t = t0                       # the clock does not reset between sorties
    order = P.lawnmower_order()
    i = start_index
    while i < len(order):
        if d.must_turn_back_since(t0):
            break
        d.fly_to(order[i], t0=t0)
        # ONLY advance the pattern if the aircraft actually GOT there.
        #
        # `fly_to` refuses a step that would strand it and returns without
        # moving. Advancing `i` regardless walks the index to the end of the
        # pattern while the drone stands still — which is what the first
        # version of this did, and it reported the lawnmower frozen at 55%
        # coverage for every sortie after the first. A flattering result
        # produced entirely by a counter.
        if d.pos != order[i]:
            break                  # resume this same cell next sortie
        i += 1
    d.go_home(use_belief=False)
    return d.finish(), i


def fly_adaptive(world, t0: float):
    """One adaptive sortie, carrying the belief map from the last one."""
    d = P.Drone(world, "adaptive")
    d.t = t0
    last_choice_t, target = -np.inf, None
    while not d.must_turn_back_since(t0):
        if target is None or d.pos == target or (d.t - last_choice_t) >= C.COMMIT_S:
            u = P.utility(world, d.pos, d.t)
            target = tuple(np.unravel_index(np.argmax(u), u.shape))
            last_choice_t = d.t
        before = d.pos
        d.fly_to(target, stop_on_find=True, t0=t0)
        if d.pos == before:
            break
        if d.pos != target:
            target = None
    d.go_home()
    return d.finish()


def campaign(seed: int, w_value: float, planner: str) -> list[dict]:
    """N_SORTIES flights over ONE persistent world."""
    world, _ = W.build(seed, w_value)
    np.random.seed(seed)
    out, t0, lawn_i = [], 0.0, 0
    for _ in range(N_SORTIES):
        if planner == "lawnmower":
            flight, lawn_i = fly_lawnmower(world, lawn_i, t0)
        else:
            flight = fly_adaptive(world, t0)
        t0 = flight.elapsed_s
        out.append({"found": world.found, "coverage": world.coverage})
    return out


def main() -> None:
    print(f"{N_SORTIES} sorties x {N_SEEDS} seeds, cumulative medians\n")
    results = {}

    for name, w_value in C.PRIOR_NOISE_LEVELS.items():
        results[name] = {}
        print(f"{name.upper()}  prior")
        print(f"  {'':10}" + "".join(f"{'sortie ' + str(k+1):>14}"
                                     for k in range(N_SORTIES)))
        for planner in ("lawnmower", "adaptive"):
            runs = [campaign(s, w_value, planner) for s in range(N_SEEDS)]
            found = [float(np.median([r[k]["found"] for r in runs]))
                     for k in range(N_SORTIES)]
            cov = [float(np.median([r[k]["coverage"] for r in runs]))
                   for k in range(N_SORTIES)]
            results[name][planner] = {"found": found, "coverage": cov}
            print(f"  {planner:<10}" + "".join(
                f"{f'{found[k]:.1f}  ({100*cov[k]:.0f}%)':>14}"
                for k in range(N_SORTIES)))
        print()

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(
        {"n_seeds": N_SEEDS, "n_sorties": N_SORTIES,
         "n_survivors": C.N_SURVIVORS, "results": results}, indent=2))

    print("found (coverage).  The question is whether adaptive's coverage keeps")
    print("climbing — if it does, skipped cells are queued, not abandoned.")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

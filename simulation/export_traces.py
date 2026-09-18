#!/usr/bin/env python3
"""
Export flight traces for the judge lab.

    python simulation/export_traces.py

Writes `simulation/lab_traces.json`, which `simulation/lab.html` replays.

WHY REPLAY AND NOT A JAVASCRIPT PORT
    The obvious build is to reimplement the planner in JS so the lab computes
    live and a judge can change anything. Two reasons not to:

    1. It would be a SECOND implementation of the algorithm. The moment either
       is edited they drift, and the lab stops showing what the 100-seed
       benchmark measured. The deck's numbers and the demo's behaviour would
       come from different code, which is the exact failure this project keeps
       catching elsewhere.

    2. CLAUDE.md's demo-day rule: if a feature can fail live on stage, it does
       not go in. The dashboard already replays a pre-computed detections.json
       for that reason. This is the same decision applied to the same problem.

    So the real Python planner runs here, records what it did through the
    `recorder` hook in planners.py, and the browser replays it. What a judge
    watches is the benchmark's own algorithm, by construction.

    The cost is real and worth stating: a judge cannot change a parameter and
    watch it re-plan. What they CAN change — prior quality — is the axis that
    matters, and all three are exported.

WHICH SEED
    The one whose adaptive result is closest to the MEDIAN across seeds, not
    the best. A demo built on a lucky seed is a demo that lies.
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
import world as W           # noqa: E402
from planners import PLANNERS   # noqa: E402

OUT = HERE / "lab_traces.json"
SEED_POOL = 40          # searched for the representative seed
BELIEF_DP = 2           # decimals kept in exported belief maps


class Recorder:
    """Collects what the planner did. Passed in; never imported by it."""

    def __init__(self) -> None:
        self.steps: list[dict] = []
        self.decisions: list[dict] = []

    def __call__(self, kind: str, **kw) -> None:
        if kind == "step":
            self.steps.append({
                "t": round(kw["t"], 2),
                "y": int(kw["y"]), "x": int(kw["x"]),
                "n": int(kw["found"]),
                **({"home": 1} if kw.get("homing") else {}),
            })
        elif kind == "decide":
            self.decisions.append({
                "t": round(kw["t"], 2),
                "from": [int(kw["frm"][0]), int(kw["frm"][1])],
                "target": [int(kw["target"][0]), int(kw["target"][1])],
                "utility": round(kw["utility"], 5),
                "belief": round(kw["belief"], 4),
                "staleness": round(kw["staleness"], 4),
                "cost_s": round(kw["cost_s"], 1),
                "belief_map": np.round(kw["belief_map"], BELIEF_DP).tolist(),
            })


def fly(seed: int, w_value: float, planner: str, record: bool):
    """One flight. `record=False` is the plain benchmark path."""
    world, corr = W.build(seed, w_value)
    np.random.seed(seed)                    # identical detection luck
    rec = Recorder() if record else None
    flight = PLANNERS[planner](world, rec) if record else PLANNERS[planner](world)
    return world, flight, rec, corr


def representative_seed(w_value: float) -> int:
    """The seed whose adaptive `found` sits closest to the median."""
    found = []
    for s in range(SEED_POOL):
        _, f, _, _ = fly(s, w_value, "adaptive", record=False)
        found.append(f.found)
    target = float(np.median(found))
    return int(np.argmin([abs(f - target) for f in found]))


def main() -> None:
    runs = []
    for name, w_value in C.PRIOR_NOISE_LEVELS.items():
        seed = representative_seed(w_value)
        print(f"  {name:<9} representative seed {seed}", flush=True)

        entry = {"prior": name, "seed": seed, "planners": {}}
        for planner in ("lawnmower", "adaptive"):
            world, flight, rec, corr = fly(seed, w_value, planner, record=True)
            entry["correlation"] = round(corr, 3)
            # `truth` and `prior_map` come from the FIRST build so both planners
            # describe one world — the lab reveals truth only after the run.
            if "truth" not in entry:
                base, _ = W.build(seed, w_value)
                entry["truth"] = base.truth.astype(int).tolist()
                entry["prior_map"] = np.round(base.belief, BELIEF_DP).tolist()
            entry["planners"][planner] = {
                "steps": rec.steps,
                "decisions": rec.decisions,
                "found": int(flight.found),
                "coverage": round(flight.coverage, 4),
                "path_m": round(flight.path_m, 1),
                "elapsed_s": round(flight.elapsed_s, 1),
                "find_times": [round(t, 2) for t in sorted(flight.find_times)],
                "t50": (lambda v: None if v is None else round(v, 1))(
                    flight.time_to_find(0.5)),
            }
            print(f"      {planner:<10} found {flight.found:2}/{C.N_SURVIVORS}"
                  f"  {len(rec.steps):4} steps  {len(rec.decisions):3} decisions",
                  flush=True)
        runs.append(entry)

    payload = {
        "meta": {
            "grid_n": C.GRID_N, "cell_m": C.CELL_M, "area_m": C.AREA_M,
            "battery_s": C.BATTERY_S, "p_detect": C.P_DETECT,
            "n_survivors": C.N_SURVIVORS, "speed_ms": C.DRONE_SPEED_MS,
            "base": list(C.BASE_CELL), "commit_s": C.COMMIT_S,
            "belief_cap": C.BELIEF_CAP, "neighbour_boost": C.NEIGHBOUR_BOOST,
            "staleness_rate": C.STALENESS_RATE,
            "seed_pool": SEED_POOL,
            "note": ("Traces produced by simulation/planners.py, the same code "
                     "the 100-seed benchmark runs. Seeds are the median case, "
                     "not the best."),
        },
        "runs": runs,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nwrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()

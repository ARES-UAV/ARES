"""
Simulation parameters for the adaptive search experiment.

READ simulation/DESIGN.md FIRST. This file is only the numbers.

TWO KINDS OF CONSTANT LIVE HERE, AND THE DIFFERENCE MATTERS
    1. Things the real system already has  — imported from backend/config.py.
       Never retyped. This project has already had one number drift across six
       files because it was written down twice; that is not repeated here.
    2. Things only the simulation has      — defined below, each tagged with
       where it came from: measured, assumed, chosen, or swept.

If a reviewer asks "where did this number come from", every line has an answer.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# ── Make backend/config.py importable ──────────────────────────────────
# simulation/ and backend/ are siblings, so Python cannot see one from the
# other by default. We add the repo root to the import path rather than
# copying constants across, because a copy is a number waiting to drift.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend import config as backend_config  # noqa: E402


# ══════════════════════════════════════════════════════════════════════
#  1. IMPORTED — the real system's numbers
# ══════════════════════════════════════════════════════════════════════

ALTITUDE_M: float = backend_config.ALTITUDE_M            # 20.0   assumed
CAMERA_FOV_DEG: float = backend_config.CAMERA_FOV_DEG    # 60.0   assumed
DRONE_SPEED_MS: float = backend_config.DRONE_SPEED_MS    # 5.0    assumed
DEVICE_FPS: float = backend_config.DEVICE_FPS            # 4.8    MEASURED
ORIGIN_LAT: float = backend_config.ORIGIN_LAT            # central Assam
ORIGIN_LON: float = backend_config.ORIGIN_LON


# ══════════════════════════════════════════════════════════════════════
#  2. DERIVED — computed, never typed
# ══════════════════════════════════════════════════════════════════════

# How wide a strip of ground the camera sees, straight down, in one frame.
#   footprint = 2 * H * tan(FOV / 2)
# At 20 m with a 60° lens this is 23.09 m. Same formula as backend/localize.py.
FOOTPRINT_M: float = 2 * ALTITUDE_M * math.tan(math.radians(CAMERA_FOV_DEG / 2))


# ══════════════════════════════════════════════════════════════════════
#  3. THE ONE MEASURED NUMBER THAT DRIVES THE ALGORITHM
# ══════════════════════════════════════════════════════════════════════

# P(detect | a person is in the observed cell).
#
# This is our recall at the shipped operating point — conf 0.18, 960 px —
# measured on 86,092 instances across 2,591 images. See
# experiments/ARES_MEASURED_NUMBERS.md.
#
# It is the reason the belief update in world.py is interesting. Because it is
# 0.824 and NOT 1.0, flying over a cell and seeing nobody does not prove the
# cell is empty — so revisiting is a real decision, not wasted fuel.
P_DETECT: float = 0.824


# ══════════════════════════════════════════════════════════════════════
#  4. THE WORLD — chosen, and the arithmetic that forced each choice
# ══════════════════════════════════════════════════════════════════════

# Cell size ≈ footprint, so ONE PASS OVER A CELL OBSERVES IT.
# With larger cells the drone would need several sweeps to cover one, and
# "observed this cell" would be a lie the simulator tells itself.
CELL_M: float = 25.0

# 20 x 20 cells of 25 m = a 500 m square = 0.25 km².
#
# Why 500 and not 1000: at DRONE_SPEED_MS for BATTERY_S the aircraft flies
# 6,000 m, sweeping 6,000 x 23.09 = 138,564 m² at absolute best. Against
# 1 km² that is 14% — the run would end having searched almost nothing. At
# 500 m it is 55%, so the drone can search about half and WHICH half it picks
# is the entire experiment.
GRID_N: int = 20
AREA_M: float = GRID_N * CELL_M

# Survivors, and how tightly they gather.
# 20 people over 400 cells is deliberately sparse — most cells are empty, which
# is what makes searching hard. CLUSTER_SIGMA is in cells: 0.8 keeps a cluster
# inside roughly a 2-3 cell radius, echoing the real clip where all 23 tracked
# people sat within 11.4 m of each other.
N_SURVIVORS: int = 20
N_CLUSTERS: int = 3
CLUSTER_SIGMA: float = 0.8

# Base station at a corner. The drone launches here and must return here.
BASE_CELL: tuple[int, int] = (0, 0)


# ══════════════════════════════════════════════════════════════════════
#  5. FLIGHT — assumed
# ══════════════════════════════════════════════════════════════════════

# 20 minutes. Realistic for a multirotor carrying a compute board and camera;
# a bare consumer drone does better, one in wind and heat does worse.
BATTERY_S: float = 1200.0

# Turn back when the remaining charge only just covers the trip home plus this
# margin. The threshold is a FUNCTION OF POSITION, not a fixed percentage —
# far from base you must turn back earlier than near it.
RESERVE_FRAC: float = 0.15

TIME_STEP_S: float = 1.0


# ══════════════════════════════════════════════════════════════════════
#  6. THE ADAPTIVE PLANNER — chosen
# ══════════════════════════════════════════════════════════════════════

# Anti-dithering. Without it the drone flips between two nearly-equal cells
# and searches nothing. Once committed to a target it stays committed for this
# many seconds unless a detection changes the picture.
#
# Exactly the problem BAND_HYSTERESIS = 0.03 solves in backend/priority.py,
# where a jittering confidence score made survivors flip between priority bands
# every frame. Same disease, same cure: require a decisive change, not any
# change.
COMMIT_S: float = 20.0

# Belief regained per second by a cell nobody has looked at.
#
# This is what ENFORCES the promise that every cell eventually gets searched.
# Without it a greedy planner can starve a whole region forever, and the claim
# "priority changes the order, not the coverage" quietly becomes false.
# At 0.0004/s an ignored cell gains ~0.48 over a full 20-minute sortie — enough
# to outrank a mildly interesting neighbour, not enough to override a strong one.
STALENESS_RATE: float = 0.0004

# Finding somebody makes the neighbours more likely, because people gather.
# One rule, several behaviours: this is what produces "search nearby after
# arriving" without any special-case code for it.
NEIGHBOUR_BOOST: float = 1.5

# Belief is never allowed to reach exactly 1.0.
#
# WHY THIS CONSTANT EXISTS — a bug found by watching coverage, not the headline
#   The Bayesian miss-update is
#       b  <-  b(1-p) / [ b(1-p) + (1-b) ]
#   At b = 1.0 that becomes 0.176 / (0.176 + 0) = 1.0. It is an ABSORBING
#   STATE: a cell pinned at certainty can never be talked out of it, however
#   many times the drone looks and finds nobody.
#
#   The neighbour boost then made that reachable. A cluster of seven people
#   fires x1.5 seven times — 17x, clipped to 1.0 — so the whole neighbourhood
#   locked at maximum attractiveness and the aircraft never left. Coverage
#   collapsed to 12.6% while the headline "found" number still looked fine.
#
#   0.95 keeps certainty out of reach, so evidence always moves belief.
BELIEF_CAP: float = 0.95


# ══════════════════════════════════════════════════════════════════════
#  7. THE EXPERIMENT — swept
# ══════════════════════════════════════════════════════════════════════

# w = how much of the prior is noise rather than signal.
#   0.0  the prior tracks the truth closely      → run A, "good"
#   0.6  half information, half junk             → run B, "mediocre"
#   1.0  pure noise, no information at all       → run C, "uniform"
#
# In a real deployment you do NOT control w — your map is as good as it is.
# We sweep it to find out how much our advantage depends on being lucky.
#
# NOTE: we report the CORRELATION between prior and truth, never w. w is
# meaningless outside this file; correlation is a standard measure anyone can
# check.
PRIOR_NOISE_LEVELS: dict[str, float] = {
    "good": 0.0,
    "mediocre": 0.6,
    "uniform": 1.0,
}

# One run proves nothing — a single lucky survivor layout can flatter either
# planner. 30 seeds, reported as median with range.
N_SEEDS: int = 30

RESULTS_DIR: Path = Path(__file__).resolve().parent / "results"


def summary() -> str:
    """One-screen sanity check. Run `python simulation/config.py`."""
    reach = DRONE_SPEED_MS * BATTERY_S
    swept = reach * FOOTPRINT_M
    return "\n".join([
        "ADAPTIVE SEARCH — CONFIGURATION",
        "",
        f"  footprint         {FOOTPRINT_M:.2f} m   (derived from {ALTITUDE_M} m, {CAMERA_FOV_DEG}°)",
        f"  cell              {CELL_M:.0f} m        (~1 pass observes 1 cell)",
        f"  grid              {GRID_N} x {GRID_N} = {GRID_N**2} cells",
        f"  area              {AREA_M:.0f} x {AREA_M:.0f} m = {AREA_M**2/1e6:.2f} km²",
        "",
        f"  battery           {BATTERY_S:.0f} s = {BATTERY_S/60:.0f} min",
        f"  flight path       {reach:,.0f} m at {DRONE_SPEED_MS} m/s",
        f"  ground swept      {swept:,.0f} m²  =  {100*swept/AREA_M**2:.1f}% of the area",
        "",
        f"  P(detect)         {P_DETECT}   MEASURED — recall at conf 0.18, 960 px",
        f"  survivors         {N_SURVIVORS} in {N_CLUSTERS} clusters",
        f"  seeds per run     {N_SEEDS}",
    ])


if __name__ == "__main__":
    print(summary())

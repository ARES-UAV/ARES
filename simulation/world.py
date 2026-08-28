"""
The world: survivors, the probability map, and what the drone learns by looking.

READ simulation/DESIGN.md FIRST.

THE ONE IDEA TO HOLD ON TO
    There are two maps, and keeping them separate is what makes the experiment
    valid.

        truth   — where the survivors actually are.  The simulator knows this.
                  The planner NEVER sees it.  Only the scoring uses it.

        belief  — what the drone thinks.  Starts as the prior, changes as it
                  flies.  This is the ONLY map the planner is allowed to read.

    If the planner ever reads `truth`, the experiment is worthless. Every
    function below is written so that cannot happen by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import config as C


# ══════════════════════════════════════════════════════════════════════
#  Building the world
# ══════════════════════════════════════════════════════════════════════

def place_survivors(rng: np.random.Generator) -> np.ndarray:
    """Scatter N_SURVIVORS across the grid in a few tight clusters.

    WHY CLUSTERS AND NOT UNIFORM RANDOM
        People gather — at shelters, on high ground, on embankments. Our own
        demo clip had all 23 tracked people within 11.4 m of each other. If we
        scattered survivors uniformly, the neighbour-boost rule would be
        useless and the adaptive planner would have nothing to exploit. Testing
        against uniform survivors would be testing against a world that does
        not happen.

    Returns an int grid: how many survivors are in each cell.
    """
    truth = np.zeros((C.GRID_N, C.GRID_N), dtype=int)

    # Cluster centres, kept off the very edge so a cluster is not half outside.
    margin = 3
    centres = rng.integers(margin, C.GRID_N - margin, size=(C.N_CLUSTERS, 2))

    for i in range(C.N_SURVIVORS):
        cy, cx = centres[i % C.N_CLUSTERS]           # deal people round-robin
        y = int(np.clip(rng.normal(cy, C.CLUSTER_SIGMA), 0, C.GRID_N - 1))
        x = int(np.clip(rng.normal(cx, C.CLUSTER_SIGMA), 0, C.GRID_N - 1))
        truth[y, x] += 1

    return truth


def blur(grid: np.ndarray, passes: int = 2) -> np.ndarray:
    """Smear a grid out with a 3x3 box average, `passes` times.

    WHY BLUR AT ALL
        A prior is never sharp. Knowing "a building here holds people" makes
        the NEIGHBOURING cells likely too — nobody knows the exact 25 m square.
        Blurring turns "3 people at (7,2)" into "this area is promising", which
        is what real prior information actually looks like.

        It also caps how good any prior can be: a blurred truth correlates
        about 0.65 with the exact point locations, never 1.0. That ceiling is
        honest, not a bug.
    """
    out = grid.astype(float).copy()
    for _ in range(passes):
        padded = np.pad(out, 1, mode="edge")
        out = sum(
            padded[i:i + C.GRID_N, j:j + C.GRID_N]
            for i in range(3) for j in range(3)
        ) / 9.0
    return out


def _normalise(g: np.ndarray) -> np.ndarray:
    """Squash a grid into 0..1. Beliefs are probabilities; they need a range."""
    lo, hi = g.min(), g.max()
    return np.full_like(g, 0.5) if hi - lo < 1e-9 else (g - lo) / (hi - lo)


def make_prior(truth: np.ndarray, w: float, rng: np.random.Generator) -> np.ndarray:
    """Build the map the drone launches with.

        prior = (1 - w) * blurred truth   +   w * random noise

    w IS THE ONLY DIAL, AND IT IS NOT A RESULT
        w = 0.0  the prior tracks the truth          → run A "good"
        w = 0.6  half signal, half junk              → run B "mediocre"
        w = 1.0  pure noise, no information at all   → run C "uniform"

        In the field you do not control w — your OSM data and hazard map are
        as good as they are. We sweep it to measure how much the result depends
        on being lucky with information.

        What gets REPORTED is correlation(prior, truth), never w. w means
        nothing outside this file.

    WHAT NOISE IS, IN THE REAL WORLD
        Not static. It is your information being wrong or stale: a building
        that collapsed last month, a relief camp pitched yesterday in what the
        map calls an empty field, an area flagged as burning that was
        evacuated hours ago.
    """
    signal = _normalise(blur(truth, passes=2))

    # Noise is blurred too. Un-blurred noise is a fine speckle that a planner
    # ignores because no region stands out; blurred noise produces convincing
    # false hotspots, which is what bad information actually does to you.
    noise = _normalise(blur(rng.random((C.GRID_N, C.GRID_N)), passes=1))

    prior = (1.0 - w) * signal + w * noise

    # Floor at 0.02: no cell is ever certainly empty before anyone has looked.
    # Capped below 1.0 so no cell starts at certainty — see BELIEF_CAP.
    return np.clip(_normalise(prior), 0.02, C.BELIEF_CAP)


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    """How well one grid predicts another. -1 to +1; 0 means it tells you nothing.

    This is the number we publish to describe prior quality, because it is
    standard and checkable. `w` is an implementation detail.
    """
    if a.std() < 1e-9 or b.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(a.ravel(), b.ravel())[0, 1])


# ══════════════════════════════════════════════════════════════════════
#  The world during a flight
# ══════════════════════════════════════════════════════════════════════

@dataclass
class World:
    """Holds both maps and applies the rules of looking.

    The planner is handed this object but is only ever allowed to read
    `belief` and `last_seen`. `truth` and `remaining` exist for scoring.
    """
    truth: np.ndarray                       # survivors per cell — HIDDEN
    belief: np.ndarray                      # what the drone thinks — VISIBLE
    remaining: np.ndarray = field(init=False)   # not yet found — HIDDEN
    last_seen: np.ndarray = field(init=False)   # time of last look — VISIBLE
    found: int = 0
    find_times: list[float] = field(default_factory=list)

    def __post_init__(self):
        self.remaining = self.truth.copy()
        # -inf, not 0, so an unvisited cell reads as "never seen" rather than
        # "seen at t=0". At t=0 those are the same; by t=600 they are not.
        self.last_seen = np.full((C.GRID_N, C.GRID_N), -np.inf)

    # ── the sensor ────────────────────────────────────────────────────
    def observe(self, y: int, x: int, t: float) -> int:
        """Look at one cell. Returns how many people were newly found.

        THE COIN FLIP
            Each undiscovered person in the cell is detected with probability
            P_DETECT = 0.824 — our measured recall. Roughly one in six is
            missed on any given pass, which is exactly why a second pass is
            worth something.

        THE BELIEF UPDATE
            Saw nobody, Bayes:

                b  <-  b(1-p) / [ b(1-p) + (1-b) ]

            Starting from b = 0.50 this gives 0.15, then 0.03, then 0.005.
            It collapses fast but never reaches zero — ONE PASS IS NOT PROOF
            OF ABSENCE. That falls straight out of a measured number rather
            than a modelling preference.

            Found somebody: neighbours go up, because people cluster. This one
            rule is what makes the drone linger in a productive area; there is
            no special-case "search nearby" code anywhere.
        """
        self.last_seen[y, x] = t
        newly = 0

        for _ in range(int(self.remaining[y, x])):
            if np.random.random() < C.P_DETECT:
                newly += 1

        if newly:
            self.remaining[y, x] -= newly
            self.found += newly
            self.find_times.extend([t] * newly)
            self._boost_neighbours(y, x)
            # This cell may still hold someone we missed, so belief stays high
            # rather than being zeroed.
            self.belief[y, x] = min(C.BELIEF_CAP, self.belief[y, x])
        else:
            b = self.belief[y, x]
            miss = 1.0 - C.P_DETECT
            self.belief[y, x] = (b * miss) / (b * miss + (1.0 - b) + 1e-12)

        return newly

    def _boost_neighbours(self, y: int, x: int) -> None:
        """A find makes the 8 surrounding cells more likely."""
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < C.GRID_N and 0 <= nx < C.GRID_N:
                    self.belief[ny, nx] = min(C.BELIEF_CAP,
                                              self.belief[ny, nx] * C.NEIGHBOUR_BOOST)

    # ── what the planner is allowed to see ────────────────────────────
    def staleness(self, t: float) -> np.ndarray:
        """Attention debt: how much a cell has earned by being ignored.

        WHY THIS EXISTS
            It is what ENFORCES the promise that priority changes the order of
            search, not its coverage. A pure greedy planner can starve a whole
            region forever — and then "we still search everywhere, just later"
            is no longer true. Growing this term guarantees an ignored cell
            eventually outranks a mildly interesting one.

        Cells never seen are treated as ignored since t=0.
        """
        age = np.where(np.isneginf(self.last_seen), t, t - self.last_seen)
        return age * C.STALENESS_RATE

    @property
    def coverage(self) -> float:
        """Fraction of cells looked at at least once. Checks the promise."""
        return float(np.sum(~np.isneginf(self.last_seen))) / (C.GRID_N ** 2)


def build(seed: int, w: float) -> tuple[World, float]:
    """Make one world. Returns it plus the prior's measured correlation.

    Same seed gives the same survivor layout every time, so both planners are
    always compared on identical worlds. Without that, a difference between
    them might just be a difference between two random maps.
    """
    rng = np.random.default_rng(seed)
    truth = place_survivors(rng)
    prior = make_prior(truth, w, rng)
    return World(truth=truth, belief=prior.copy()), correlation(prior, truth)


if __name__ == "__main__":
    print("PRIOR QUALITY BY NOISE LEVEL — 30 seeds each\n")
    print(f"  {'run':<10} {'w':>5}   {'correlation with truth':>24}")
    print("  " + "-" * 44)
    for name, w in C.PRIOR_NOISE_LEVELS.items():
        cs = [build(s, w)[1] for s in range(C.N_SEEDS)]
        print(f"  {name:<10} {w:>5.1f}   {np.median(cs):>12.3f}   "
              f"[{np.min(cs):+.2f} .. {np.max(cs):+.2f}]")

    w0, _ = build(0, 0.0)
    print(f"\n  survivors placed: {w0.truth.sum()}  "
          f"in {np.count_nonzero(w0.truth)} of {C.GRID_N**2} cells")

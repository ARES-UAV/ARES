"""
The two search strategies, and the flight simulator they both run inside.

READ simulation/DESIGN.md FIRST.

WHAT IS BEING COMPARED
    lawnmower  — fly the grid in fixed order. What most UAV search does today.
    adaptive   — fly where expected finds per second is highest.

    Both use the SAME flight simulator, the same battery, the same sensor, the
    same survivor layout. The only difference is which cell they pick next. If
    anything else differed, a gap between them would not mean anything.

THE RULE THAT KEEPS THIS HONEST
    A planner may read `world.belief` and `world.last_seen`.
    A planner may NEVER read `world.truth` or `world.remaining`.
    Those exist only for scoring, after the flight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

import config as C
from world import World


# ══════════════════════════════════════════════════════════════════════
#  Geometry
# ══════════════════════════════════════════════════════════════════════

def metres(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Straight-line distance between two cell centres, in metres."""
    return math.hypot(a[0] - b[0], a[1] - b[1]) * C.CELL_M


def travel_time(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Seconds to fly from cell a to cell b at cruise speed."""
    return metres(a, b) / C.DRONE_SPEED_MS


def line_cells(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    """Every cell the aircraft passes through flying from a to b.

    THIS FUNCTION IS THE WHOLE "SEARCH WHAT IS UNDERNEATH" IDEA
        The camera does not switch off between waypoints. Flying from cell 1
        to cell 25 means overflying everything in between, and each of those
        cells is genuinely observed — a person there gets the same 0.824 roll
        as one at the destination.

        A planner that treats travel as dead time throws those observations
        away and revisits ground it has already covered. Bresenham's line
        algorithm gives us the cells crossed; the flight loop then observes
        each one.

    Excludes the starting cell (already observed) and includes the destination.
    """
    (y0, x0), (y1, x1) = a, b
    cells: list[tuple[int, int]] = []
    dy, dx = abs(y1 - y0), abs(x1 - x0)
    sy, sx = (1 if y0 < y1 else -1), (1 if x0 < x1 else -1)
    err = dx - dy
    y, x = y0, x0

    while (y, x) != (y1, x1):
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        cells.append((y, x))

    return cells


# ══════════════════════════════════════════════════════════════════════
#  What a flight produces
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Flight:
    planner: str
    found: int = 0
    total_survivors: int = 0
    find_times: list[float] = field(default_factory=list)
    coverage: float = 0.0
    path_m: float = 0.0
    elapsed_s: float = 0.0
    returned_home: bool = False
    path: list[tuple[int, int]] = field(default_factory=list)

    def time_to_find(self, fraction: float) -> float | None:
        """When did we reach this fraction of all survivors? None if never.

        WHY FRACTIONS AND NOT A SINGLE TOTAL
            In rescue an early find is worth more than a late one. A planner
            that reaches 80% in half the time is a large win even if both
            eventually find the same number — and one total-time figure would
            hide that completely.
        """
        need = math.ceil(fraction * self.total_survivors)
        if need == 0 or len(self.find_times) < need:
            return None
        return sorted(self.find_times)[need - 1]


# ══════════════════════════════════════════════════════════════════════
#  The flight simulator — shared by both planners
# ══════════════════════════════════════════════════════════════════════

class Drone:
    """Position, battery, and the act of flying somewhere while looking down."""

    def __init__(self, world: World, planner_name: str):
        self.w = world
        self.pos = C.BASE_CELL
        self.t = 0.0
        self.flight = Flight(planner=planner_name,
                             total_survivors=int(world.truth.sum()))
        self.flight.path.append(self.pos)
        self.w.observe(*self.pos, self.t)     # look at the launch cell

    # ── battery ───────────────────────────────────────────────────────
    @property
    def remaining(self) -> float:
        return C.BATTERY_S - self.t

    def must_turn_back(self, frm: tuple[int, int] | None = None) -> bool:
        """Is there only just enough charge left to get home?

        THE THRESHOLD IS A FUNCTION OF POSITION, NOT A FIXED PERCENTAGE
            Deep in the search area you must turn back earlier than you would
            near base. A flat "return at 20%" rule strands the aircraft.
        """
        frm = frm or self.pos
        return self.remaining <= travel_time(frm, C.BASE_CELL) * (1 + C.RESERVE_FRAC)

    # ── the core action ───────────────────────────────────────────────
    def fly_to(self, target: tuple[int, int], *, stop_on_find: bool = False) -> int:
        """Fly to a cell, observing every cell crossed on the way.

        Returns how many people were found en route. Stops early if the
        battery reaches its return threshold — the aircraft is never allowed
        to fly itself into a position it cannot come home from.
        """
        found_here = 0

        for cell in line_cells(self.pos, target):
            step_s = travel_time(self.pos, cell)

            # Refuse the step if taking it would strand us.
            if self.remaining - step_s <= travel_time(cell, C.BASE_CELL) * (1 + C.RESERVE_FRAC):
                return found_here

            self.t += step_s
            self.flight.path_m += metres(self.pos, cell)
            self.pos = cell
            self.flight.path.append(cell)

            n = self.w.observe(cell[0], cell[1], self.t)
            found_here += n

            if n and stop_on_find:
                return found_here

        return found_here

    def go_home(self) -> None:
        """Return to base — and keep searching the whole way.

        THE RETURN LEG IS NOT DEAD TIME
            A straight line home observes whatever happens to lie on it. A
            greedy walk that prefers high-belief neighbours, while still
            closing the distance to base, covers better ground for the same
            fuel. That is the only difference between this and a straight run.
        """
        guard = 0
        while self.pos != C.BASE_CELL and guard < C.GRID_N * 4:
            guard += 1
            here_d = metres(self.pos, C.BASE_CELL)

            best, best_score = None, -np.inf
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = self.pos[0] + dy, self.pos[1] + dx
                    if not (0 <= ny < C.GRID_N and 0 <= nx < C.GRID_N):
                        continue
                    # Only steps that actually bring us closer to base.
                    if metres((ny, nx), C.BASE_CELL) >= here_d:
                        continue
                    score = self.w.belief[ny, nx]
                    if score > best_score:
                        best, best_score = (ny, nx), score

            if best is None:
                break

            step_s = travel_time(self.pos, best)
            self.t += step_s
            self.flight.path_m += metres(self.pos, best)
            self.pos = best
            self.flight.path.append(best)
            self.w.observe(best[0], best[1], self.t)

        self.flight.returned_home = (self.pos == C.BASE_CELL)

    def finish(self) -> Flight:
        f = self.flight
        f.found = self.w.found
        f.find_times = list(self.w.find_times)
        f.coverage = self.w.coverage
        f.elapsed_s = self.t
        return f


# ══════════════════════════════════════════════════════════════════════
#  Planner 1 — Lawnmower  (the baseline)
# ══════════════════════════════════════════════════════════════════════

def lawnmower_order() -> list[tuple[int, int]]:
    """Boustrophedon: row 0 left-to-right, row 1 right-to-left, and so on.

    Named after ox-ploughing. It is the standard coverage pattern and what
    most UAV search flies today, which is exactly why it is the baseline.
    """
    order: list[tuple[int, int]] = []
    for y in range(C.GRID_N):
        xs = range(C.GRID_N) if y % 2 == 0 else range(C.GRID_N - 1, -1, -1)
        order.extend((y, x) for x in xs)
    return order


def run_lawnmower(world: World) -> Flight:
    """Fly the fixed pattern until the battery says come home.

    Reads neither the prior nor any detection. It cannot adapt — that is the
    point of it.
    """
    d = Drone(world, "lawnmower")
    for cell in lawnmower_order():
        if d.must_turn_back():
            break
        d.fly_to(cell)
    d.go_home()
    return d.finish()


# ══════════════════════════════════════════════════════════════════════
#  Planner 2 — Adaptive
# ══════════════════════════════════════════════════════════════════════

def utility(world: World, frm: tuple[int, int], t: float) -> np.ndarray:
    """Score every cell. Higher is more worth flying to.

            utility  =  ( belief + staleness )  /  ( travel_time + search_time )

    THREE BEHAVIOURS FALL OUT OF THIS ONE LINE

    1. EXPECTED FINDS PER SECOND, not per cell. Dividing by travel time means
       a slightly-worse cell that is much closer can win. This is what makes
       the drone sweep the area around a find instead of darting across the
       map — the "search nearby first" behaviour, as arithmetic rather than a
       special case.

    2. COVERAGE IS GUARANTEED, not hoped for. Staleness grows with time since
       a cell was last observed, so an ignored cell eventually outranks a
       mildly interesting one. Without this a greedy planner can starve a
       region forever, and the claim "priority changes the order, not the
       coverage" quietly stops being true.

    3. NO PEEKING. It reads belief and last_seen. It never touches truth.
    """
    search_s = C.CELL_M / C.DRONE_SPEED_MS

    yy, xx = np.mgrid[0:C.GRID_N, 0:C.GRID_N]
    dist_m = np.hypot(yy - frm[0], xx - frm[1]) * C.CELL_M
    cost_s = dist_m / C.DRONE_SPEED_MS + search_s

    value = world.belief + world.staleness(t)

    u = value / cost_s
    u[frm] = -np.inf          # never pick the cell we are already on
    return u


def run_adaptive(world: World) -> Flight:
    """Fly to wherever the expected payoff per second is highest.

    COMMITMENT
        Re-choosing every second makes the aircraft dither between two
        near-equal cells and search nothing. It commits to a target for
        COMMIT_S seconds unless it finds somebody — a find changes the map
        enough to justify rethinking immediately.

        This is the same problem BAND_HYSTERESIS = 0.03 solves in
        backend/priority.py, where a jittering confidence score flipped
        survivors between priority bands every frame. Require a decisive
        change, not any change.
    """
    d = Drone(world, "adaptive")
    last_choice_t = -np.inf
    target: tuple[int, int] | None = None

    while not d.must_turn_back():
        need_new = (
            target is None
            or d.pos == target
            or (d.t - last_choice_t) >= C.COMMIT_S
        )
        if need_new:
            u = utility(world, d.pos, d.t)
            target = tuple(np.unravel_index(np.argmax(u), u.shape))
            last_choice_t = d.t

        before = d.pos
        # stop_on_find: a detection reshapes the belief map, so re-plan at once
        d.fly_to(target, stop_on_find=True)

        if d.pos == before:      # could not move — battery, or already there
            break
        if d.pos != target:      # stopped early on a find
            target = None

    d.go_home()
    return d.finish()


PLANNERS = {"lawnmower": run_lawnmower, "adaptive": run_adaptive}

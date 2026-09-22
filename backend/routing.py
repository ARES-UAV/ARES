"""Safe access routes from the rescue staging point to each survivor.

`simulation/planners.py` plans where the DRONE flies. This plans where the
RESCUE TEAM walks, and the two are different problems that a judge will
otherwise assume are the same one:

    drone    flies over everything, optimises for finding people fast
    team     goes around hazards on the ground, optimises for arriving safely

So this module does not reuse the planner. It builds a ground-cost grid from
the known hazards and runs A* from the staging point to each confirmed
survivor, in the order the priority score already ranks them.

── What a "safe" route actually means here ────────────────────────
Two paths are computed for every survivor:

    direct    the shortest path, ignoring hazard risk entirely
    safe      the lowest-cost path, where cost = 1 + ROUTE_HAZARD_WEIGHT * risk

The DIFFERENCE between them is the feature. A safe route that is 12 m longer
and keeps the team out of a cell at risk 0.8 is a decision someone made on
evidence; a single line on a map is just a line. The dashboard draws both.

── Honest limits, stated here because the map cannot state them ───
The cost surface is a hazard grid derived from aerial imagery. It is NOT a
road network, a footpath graph or a passability survey. A route here is a
risk-avoidance corridor — "go this way round rather than that way" — and not
turn-by-turn navigation. Calling it the latter would claim a map we do not
have.

The grid is also only as real as `config.HAZARDS`. While that list is empty —
hazard classification is Phase 2 — there is no risk surface at all, both paths
are identical, and `hazard_aware` comes back False. That follows the same
convention as the priority score's hazard term: a term that was never scored
is reported as absent, never as zero. "No hazards known" must not render as
"the area is clear."
"""

import heapq
import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from backend import config
from backend.localize import METRES_PER_DEGREE_LAT

Cell = Tuple[int, int]
LatLon = Tuple[float, float]

# Eight-connected movement. Diagonals cost sqrt(2) so that a diagonal step is
# not a cheaper way of covering the same ground than two orthogonal ones —
# without it A* produces staircase routes that are shorter on paper than in
# metres, and the reported length would be wrong.
_NEIGHBOURS: Tuple[Tuple[int, int, float], ...] = (
    (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
    (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0)),
    (-1, 1, math.sqrt(2.0)), (-1, -1, math.sqrt(2.0)),
)


class LocalFrame:
    """Flat east/north metres about a reference latitude and longitude.

    Routing needs a metric grid; the survivors arrive as latitude/longitude.
    Over the few hundred metres a clip covers, a flat projection about a single
    reference point is exact enough that the error is far below the cell size —
    and unlike `localize`'s per-frame origin, this frame does not move, so a
    distance measured in it is a real distance and not an artifact of the
    assumed flight track.
    """

    def __init__(self, ref_lat: float, ref_lon: float) -> None:
        self.ref_lat = ref_lat
        self.ref_lon = ref_lon
        self._m_per_deg_lon = METRES_PER_DEGREE_LAT * math.cos(math.radians(ref_lat))

    def to_local(self, lat: float, lon: float) -> Tuple[float, float]:
        """(latitude, longitude) -> (east metres, north metres)."""
        return (
            (lon - self.ref_lon) * self._m_per_deg_lon,
            (lat - self.ref_lat) * METRES_PER_DEGREE_LAT,
        )

    def to_latlon(self, east_m: float, north_m: float) -> LatLon:
        """(east metres, north metres) -> (latitude, longitude)."""
        return (
            self.ref_lat + north_m / METRES_PER_DEGREE_LAT,
            self.ref_lon + east_m / self._m_per_deg_lon,
        )


class RiskGrid:
    """A ground-cost surface over the area the survivors occupy.

    Cell size is `config.ROUTE_CELL_M`; the extent is the bounding box of the
    staging point and every survivor, padded by `config.ROUTE_MARGIN_M` so a
    route has room to go AROUND a hazard rather than being boxed in by the
    edge of the grid — a detour that leaves the grid would otherwise be
    reported as "no route", which is a false negative, not a hazard.
    """

    def __init__(self, frame: LocalFrame, points: Sequence[Tuple[float, float]]) -> None:
        self.frame = frame
        self.cell_m = float(config.ROUTE_CELL_M)
        margin = float(config.ROUTE_MARGIN_M)

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        self.x0 = min(xs) - margin
        self.y0 = min(ys) - margin
        self.nx = max(1, int(math.ceil((max(xs) + margin - self.x0) / self.cell_m)))
        self.ny = max(1, int(math.ceil((max(ys) + margin - self.y0) / self.cell_m)))

        # Hazards in local metres. Empty until the classifier lands, which is
        # the case this module has to stay honest about.
        self.hazards: List[Tuple[float, float]] = [
            frame.to_local(lat, lon) for lat, lon in config.HAZARDS
        ]
        self.hazard_aware = bool(self.hazards)
        self._risk: Dict[Cell, float] = {}

    # ── geometry ───────────────────────────────────────────────────
    def cell_of(self, east_m: float, north_m: float) -> Cell:
        i = min(self.nx - 1, max(0, int((east_m - self.x0) / self.cell_m)))
        j = min(self.ny - 1, max(0, int((north_m - self.y0) / self.cell_m)))
        return i, j

    def centre_of(self, cell: Cell) -> Tuple[float, float]:
        i, j = cell
        return (self.x0 + (i + 0.5) * self.cell_m, self.y0 + (j + 0.5) * self.cell_m)

    def in_bounds(self, cell: Cell) -> bool:
        i, j = cell
        return 0 <= i < self.nx and 0 <= j < self.ny

    # ── cost ───────────────────────────────────────────────────────
    def risk(self, cell: Cell) -> float:
        """0.0 clear, 1.0 at a hazard, linear in between.

        Deliberately the same shape as the hazard term in `backend.priority`:
        full strength at the hazard, falling to nothing at
        `config.HAZARD_INFLUENCE_M`. One decay rule for the whole system means
        a survivor ranked "close to a hazard" and a route that avoids that
        hazard are talking about the same geometry, not two similar-sounding
        ones that disagree at the edges.
        """
        if not self.hazards:
            return 0.0
        cached = self._risk.get(cell)
        if cached is not None:
            return cached
        ex, ny = self.centre_of(cell)
        nearest = min(math.hypot(ex - hx, ny - hy) for hx, hy in self.hazards)
        value = max(0.0, 1.0 - nearest / float(config.HAZARD_INFLUENCE_M))
        self._risk[cell] = value
        return value

    def blocked(self, cell: Cell) -> bool:
        """Cells too close to a hazard to walk through at all.

        A soft penalty alone lets A* march straight through a fire if the
        detour is long enough, which is not a trade a rescue team would make.
        """
        if not self.hazards:
            return False
        ex, ny = self.centre_of(cell)
        block = float(config.ROUTE_HAZARD_BLOCK_M)
        return any(math.hypot(ex - hx, ny - hy) <= block for hx, hy in self.hazards)

    def step_cost(self, cell: Cell, hazard_weight: float) -> float:
        """Multiplier on a step INTO `cell`. 1.0 on clear ground."""
        return 1.0 + hazard_weight * self.risk(cell)


def _astar(grid: RiskGrid, start: Cell, goal: Cell, hazard_weight: float) -> Optional[List[Cell]]:
    """Least-cost path from `start` to `goal`, or None if the goal is walled in.

    The heuristic is straight-line distance in cells, which is admissible
    because the cheapest possible step multiplier is 1.0 — no cell is ever
    cheaper than clear ground, so the heuristic can never overestimate and A*
    still returns the true optimum.

    `start` and `goal` are never treated as blocked, whatever the risk field
    says. A survivor detected inside a hazard zone is exactly the person the
    system exists to reach; refusing to plan a route to them because the
    destination is dangerous would be a bug that reads as a safety feature.
    """
    if start == goal:
        return [start]

    open_heap: List[Tuple[float, float, Cell]] = [(0.0, 0.0, start)]
    came: Dict[Cell, Cell] = {}
    best: Dict[Cell, float] = {start: 0.0}

    def h(cell: Cell) -> float:
        return math.hypot(cell[0] - goal[0], cell[1] - goal[1])

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current == goal:
            path = [current]
            while current in came:
                current = came[current]
                path.append(current)
            path.reverse()
            return path
        if g > best.get(current, math.inf):
            continue
        for di, dj, step in _NEIGHBOURS:
            nxt = (current[0] + di, current[1] + dj)
            if not grid.in_bounds(nxt):
                continue
            if nxt != goal and grid.blocked(nxt):
                continue
            g2 = g + step * grid.step_cost(nxt, hazard_weight)
            if g2 < best.get(nxt, math.inf) - 1e-9:
                best[nxt] = g2
                came[nxt] = current
                heapq.heappush(open_heap, (g2 + h(nxt), g2, nxt))
    return None


def _path_metrics(grid: RiskGrid, path: Sequence[Cell]) -> Tuple[float, float, float]:
    """(length in metres, peak risk, mean risk) along a cell path."""
    if not path:
        return 0.0, 0.0, 0.0
    length = 0.0
    for a, b in zip(path, path[1:]):
        ax, ay = grid.centre_of(a)
        bx, by = grid.centre_of(b)
        length += math.hypot(bx - ax, by - ay)
    risks = [grid.risk(c) for c in path]
    return length, max(risks), sum(risks) / len(risks)


def _to_latlon_path(grid: RiskGrid, path: Sequence[Cell]) -> List[LatLon]:
    return [grid.frame.to_latlon(*grid.centre_of(c)) for c in path]


def staging_point() -> LatLon:
    """Where the rescue team sets out from.

    Defaults to the clip's GPS origin — the drone's position at frame 0, which
    is also where an operator launching it would be standing. It is a
    configured constant of exactly the same kind as `ALTITUDE_M`: assumed and
    disclosed, not measured, because the prototype has no way to know where a
    real staging area would be.
    """
    if config.ROUTE_BASE_LAT is None or config.ROUTE_BASE_LON is None:
        return config.ORIGIN_LAT, config.ORIGIN_LON
    return config.ROUTE_BASE_LAT, config.ROUTE_BASE_LON


def plan_routes(survivors: Iterable[object]) -> List[dict]:
    """One route per survivor, highest priority first.

    `survivors` is any iterable of objects carrying `track_id`, `latitude`,
    `longitude`, `priority` and `priority_band` — the `Survivor` model does,
    and taking it structurally keeps this module testable without the API.

    Returns plain dicts; `backend.main` wraps them in the `Route` model. The
    ordering is the priority ordering, so the route list and the rescue queue
    are the same sequence rather than two lists a reader has to reconcile.
    """
    people = [s for s in survivors if s is not None]
    if not people:
        return []

    base_lat, base_lon = staging_point()
    frame = LocalFrame(base_lat, base_lon)

    points = [frame.to_local(base_lat, base_lon)]
    points += [frame.to_local(s.latitude, s.longitude) for s in people]
    # Hazards belong inside the grid too: one sitting just outside the
    # survivors' bounding box still shapes the route between them.
    points += [frame.to_local(lat, lon) for lat, lon in config.HAZARDS]

    grid = RiskGrid(frame, points)
    start = grid.cell_of(*frame.to_local(base_lat, base_lon))
    weight = float(config.ROUTE_HAZARD_WEIGHT)

    out: List[dict] = []
    for s in sorted(people, key=lambda p: (-p.priority, p.track_id)):
        goal = grid.cell_of(*frame.to_local(s.latitude, s.longitude))

        safe = _astar(grid, start, goal, weight)
        direct = _astar(grid, start, goal, 0.0)
        if safe is None or direct is None:
            # Only reachable if the grid is degenerate; recorded rather than
            # silently dropped so a missing route is visible on the dashboard.
            out.append({
                "track_id": s.track_id,
                "priority": s.priority,
                "priority_band": s.priority_band,
                "reachable": False,
                "hazard_aware": grid.hazard_aware,
                "path": [],
                "direct_path": [],
                "length_m": 0.0,
                "direct_length_m": 0.0,
                "detour_m": 0.0,
                "risk_max": 0.0,
                "risk_mean": 0.0,
                "direct_risk_max": 0.0,
            })
            continue

        s_len, s_max, s_mean = _path_metrics(grid, safe)
        d_len, d_max, _ = _path_metrics(grid, direct)
        out.append({
            "track_id": s.track_id,
            "priority": s.priority,
            "priority_band": s.priority_band,
            "reachable": True,
            # False means the risk term was never scored — no hazards are
            # known — so `path` and `direct_path` are necessarily identical.
            # It does not mean the ground is safe.
            "hazard_aware": grid.hazard_aware,
            "path": _to_latlon_path(grid, safe),
            "direct_path": _to_latlon_path(grid, direct),
            "length_m": round(s_len, 1),
            "direct_length_m": round(d_len, 1),
            # What avoiding the hazards cost. Zero while no hazards are known.
            "detour_m": round(s_len - d_len, 1),
            "risk_max": round(s_max, 3),
            "risk_mean": round(s_mean, 3),
            # The peak risk the shortest path would have walked the team
            # through. This is the number that justifies the detour.
            "direct_risk_max": round(d_max, 3),
        })
    return out

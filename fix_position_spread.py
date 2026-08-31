#!/usr/bin/env python3
"""
Post-merge fix: make `position_spread_m` measure the projection, not the
assumed flight track. Plus one cross-module private import.

    python fix_position_spread.py          # apply
    python fix_position_spread.py --check  # show what would change, touch nothing

WHY
    `position_spread_m` is computed from positions projected with the MOVING
    origin, which advances along an ASSUMED 5 m/s track. Over a track's
    lifetime that assumption dominates the number:

        assumed drone travel     20.8 cm/frame   (5.0 m/s / 24 fps)
        measured, moving origin  19.9 cm/frame
        measured, fixed frame     1.8 cm/frame   = 1.0 px at GSD 1.80 cm/px

    So the metric reads 5.60-20.22 m and correlates +0.930 with how long the
    track lived. It is measuring the assumption, not the geometry.

    The guide's §6② says to use `bbox_to_latlon` here. That instruction
    contradicts Rule 1 in the same document: relative measurements use the
    fixed frame, and the distance between two estimates OF ONE PERSON is a
    relative measurement — failing for exactly the reason Rule 1 exists.

    Robin implemented §6② correctly. The spec was wrong.

WHAT CHANGES
    The map pin keeps the moving origin — it is an absolute position and that
    is right. Only the SPREAD moves to the fixed frame, where it becomes
    0.45-4.12 m and can actually catch a wrong altitude or frame width.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
MAIN = REPO / "backend" / "main.py"
EVENTS = REPO / "backend" / "events.py"
PRIORITY = REPO / "backend" / "priority.py"

CHECK = "--check" in sys.argv


# ── 1. collect reference-frame positions alongside the absolute ones ──
OLD_COLLECT = """        positions_by_track.setdefault(track_id, []).append(
            localize.bbox_to_latlon(detection.bbox, detection.frame_id)
        )
"""
NEW_COLLECT = """        positions_by_track.setdefault(track_id, []).append(
            localize.bbox_to_latlon(detection.bbox, detection.frame_id)
        )

        # The same detection with the assumed flight track held still. The
        # SPREAD is measured in here, not in the absolute positions above —
        # see the block that computes it for why.
        reference_by_track.setdefault(track_id, []).append(
            localize.bbox_to_reference_latlon(detection.bbox)
        )
"""

OLD_DECL = """    positions_by_track: Dict[int, List[Tuple[float, float]]] = {}
"""
NEW_DECL = """    positions_by_track: Dict[int, List[Tuple[float, float]]] = {}
    reference_by_track: Dict[int, List[Tuple[float, float]]] = {}
"""


# ── 2. compute the spread in the fixed frame ─────────────────────────
OLD_SPREAD = """    # `position_spread_m` is the furthest any single estimate sat from that
    # median — the most useful diagnostic this module produces. Centimetres
    # means the projection agrees with itself; tens of metres means altitude or
    # frame width is wrong, and it is caught here before someone checks a pin
    # against a map. It is absolute geometry (`bbox_to_latlon`), like the pin it
    # describes, never the reference-frame projection.
    median_position: Dict[int, Tuple[float, float]] = {}
    position_spread: Dict[int, float] = {}
    for track_id in track_ids:
        points = positions_by_track[track_id]
        lat = statistics.median(p[0] for p in points)
        lon = statistics.median(p[1] for p in points)
        median_position[track_id] = (lat, lon)
        position_spread[track_id] = max(
            priority.metres_between(lat, lon, pt[0], pt[1]) for pt in points
        )
"""
NEW_SPREAD = '''    # `position_spread_m` is the furthest any single estimate sat from the
    # median of that track's estimates — how much the projection disagrees
    # with itself about one stationary person.
    #
    # IT IS MEASURED IN THE FIXED REFERENCE FRAME, NOT AGAINST THE PIN.
    #
    # Measured on the demo clip, frame-to-frame displacement of the same
    # tracks under the two projections:
    #
    #     assumed drone travel      20.8 cm/frame   (5 m/s / 24 fps)
    #     moving origin             19.9 cm/frame
    #     fixed reference frame      1.8 cm/frame   = 1.0 px at GSD 1.80 cm/px
    #
    # The moving origin advances along an ASSUMED track, so over a track's
    # lifetime the spread it produces is that assumption integrated over time —
    # 5.60 to 20.22 m, correlating +0.930 with how long the track lived. It
    # cannot distinguish a wrong altitude from a long track, which is the one
    # job it exists to do.
    #
    # This is Rule 1, applied where the guide's §6② said not to: the distance
    # between two estimates OF ONE PERSON is a relative measurement, and
    # relative measurements use the fixed frame. In it the spread reads
    # 0.45-4.12 m and a scale error would show.
    #
    # The PIN stays absolute. Where somebody is and how well we know it are
    # different questions and take different projections.
    median_position: Dict[int, Tuple[float, float]] = {}
    position_spread: Dict[int, float] = {}
    for track_id in track_ids:
        points = positions_by_track[track_id]
        lat = statistics.median(p[0] for p in points)
        lon = statistics.median(p[1] for p in points)
        median_position[track_id] = (lat, lon)

        fixed = reference_by_track[track_id]
        ref_lat = statistics.median(p[0] for p in fixed)
        ref_lon = statistics.median(p[1] for p in fixed)
        position_spread[track_id] = max(
            priority.metres_between(ref_lat, ref_lon, pt[0], pt[1]) for pt in fixed
        )
'''


# ── 3. the private import across modules ─────────────────────────────
RENAMES = [
    (PRIORITY, "def _squared_metres(", "def squared_metres("),
    (PRIORITY, "                _squared_metres(lat0, longitude, other_lat, other_lon)",
     "                squared_metres(lat0, longitude, other_lat, other_lon)"),
    (EVENTS, "from backend.priority import _squared_metres",
     "from backend.priority import squared_metres"),
    (EVENTS, "                _squared_metres(", "                squared_metres("),
]


def edit(path: Path, pairs: list[tuple[str, str]]) -> int:
    if not path.is_file():
        sys.exit(f"not found: {path}\nRun this from the repo root, after merging.")
    s = path.read_text()
    n = 0
    for old, new in pairs:
        if new in s and old not in s:
            print(f"  · already applied in {path.name}: {old.strip()[:52]}")
            continue
        if old not in s:
            sys.exit(f"\nPattern not found in {path.name}:\n  {old.strip()[:70]}\n"
                     f"The file differs from what was reviewed. Stop and re-diff.")
        s = s.replace(old, new, 1)
        n += 1
    if n and not CHECK:
        path.write_text(s)
    return n


def main() -> None:
    print(f"{'CHECK — nothing will be written' if CHECK else 'Applying'}\n")

    n = edit(MAIN, [(OLD_DECL, NEW_DECL),
                    (OLD_COLLECT, NEW_COLLECT),
                    (OLD_SPREAD, NEW_SPREAD)])
    print(f"  backend/main.py      {n} edit(s) — spread moves to the fixed frame")

    by_file: dict[Path, list] = {}
    for path, old, new in RENAMES:
        by_file.setdefault(path, []).append((old, new))
    for path, pairs in by_file.items():
        n = edit(path, pairs)
        print(f"  backend/{path.name:<12} {n} edit(s) — _squared_metres is now public")

    print("\nThen re-verify:")
    print("  uvicorn backend.main:app --port 8000")
    print("  python tools/verify_branch.py")
    print("\nposition_spread_m should read about 0.45-4.12 m, and the WARN clears.")


if __name__ == "__main__":
    main()

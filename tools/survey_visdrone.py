#!/usr/bin/env python3
"""
Rank VisDrone-VID sequences by how many people are in them.

    python tools/survey_visdrone.py ~/Downloads/VisDrone2019-VID-val

Several VisDrone sequences are motorways — a clip full of cars demonstrates
nothing about survivor detection. valset ships ground-truth annotations, so
this picks the crowded ones from data rather than by scrolling thumbnails.

VisDrone annotation columns:
    frame, target_id, x, y, w, h, score, category, truncation, occlusion
Category 1 = pedestrian, 2 = people. Everything else is vehicles and bikes.
"""

import sys
import glob
from pathlib import Path
from collections import defaultdict

PERSON_CATEGORIES = {1, 2}
MIN_FRAMES = 320          # need 13 s at 24 fps, with headroom


def find_root(given: Path) -> Path:
    """VisDrone zips nest a folder; find the one holding sequences/."""
    if (given / "sequences").is_dir():
        return given
    for candidate in given.rglob("sequences"):
        if candidate.is_dir():
            return candidate.parent
    sys.exit(f"No 'sequences' directory found under {given}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    root = find_root(Path(sys.argv[1]).expanduser())
    ann_dir = root / "annotations"
    seq_dir = root / "sequences"

    if not ann_dir.is_dir():
        sys.exit(f"No annotations/ under {root} — is this the val set?")

    print(f"root: {root}\n")

    rows = []
    for ann in sorted(ann_dir.glob("*.txt")):
        per_frame = defaultdict(int)
        with open(ann) as fh:
            for line in fh:
                parts = line.strip().split(",")
                if len(parts) < 8:
                    continue
                try:
                    if int(parts[7]) in PERSON_CATEGORIES:
                        per_frame[int(parts[0])] += 1
                except ValueError:
                    continue

        if not per_frame:
            continue

        name = ann.stem
        n_frames = len(glob.glob(str(seq_dir / name / "*.jpg")))
        if n_frames < MIN_FRAMES:
            continue

        rows.append({
            "avg": sum(per_frame.values()) / len(per_frame),
            "peak": max(per_frame.values()),
            "frames": n_frames,
            "name": name,
        })

    if not rows:
        sys.exit("No sequences with people and enough frames. Wrong dataset?")

    rows.sort(key=lambda r: r["avg"], reverse=True)

    print(f"{'people/frame':>12} {'peak':>6} {'frames':>7}   sequence")
    print("-" * 62)
    for r in rows[:15]:
        print(f"{r['avg']:>12.1f} {r['peak']:>6} {r['frames']:>7}   {r['name']}")

    best = rows[0]
    print(f"\nSuggested: {best['name']}  "
          f"({best['avg']:.1f} people/frame, {best['frames']} frames)")
    print(f"\nLook at it before committing:")
    print(f"  open '{seq_dir / best['name']}'")
    print(f"\nThen:")
    print(f"  python tools/build_demo_clip.py {sys.argv[1]} {best['name']}")


if __name__ == "__main__":
    main()
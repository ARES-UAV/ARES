#!/usr/bin/env python3
"""
Work out how many of your track IDs are real people.

    python tools/analyse_tracks.py

Reads backend/data/detections.json and answers three questions:

  1. How many survivors survive each persistence threshold?
  2. Are the short tracks false positives, or real people at the frame edge?
  3. What should min_frames actually be?

A raw unique-track count is not a survivor count. Three different things
inflate it, and they need different fixes:

  FLICKER      a shadow or bag that reads person-shaped for one frame.
               Short, LOW confidence, anywhere in frame.
               -> persistence filtering removes this.

  FRAME EDGE   a real person walking into or out of view.
               Short, NORMAL confidence, near the image boundary.
               -> NOT a false positive. Filtering these loses real people.

  ID SWITCH    one person who got a new ID after an occlusion.
               Medium length, NORMAL confidence, middle of frame.
               -> persistence filtering does NOT fix this. Needs a better
                  tracker (BoT-SORT) or accepting the over-count.

Telling them apart is what decides whether min_frames is the right lever.
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DETECTIONS = REPO / "backend" / "data" / "detections.json"

FRAME_W, FRAME_H = 1280, 720
EDGE_MARGIN = 60          # px from any boundary counts as "at the edge"
SHORT_TRACK = 3           # frames; at/below this is "short"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DETECTIONS
    if not path.exists():
        sys.exit(f"No detections at {path}")

    dets = json.loads(path.read_text())
    print(f"file             {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")
    print(f"raw detections   {len(dets)}")

    tracks = defaultdict(list)
    untracked = 0
    for d in dets:
        if d["track_id"] == -1:
            untracked += 1
        else:
            tracks[d["track_id"]].append(d)

    n_frames = max(d["frame_id"] for d in dets) + 1
    print(f"frames           {n_frames}")
    print(f"unique track IDs {len(tracks)}")
    print(f"untracked (-1)   {untracked}")
    print(f"avg per frame    {len(dets)/n_frames:.1f}")

    # ── 1. The persistence curve ─────────────────────────────────────
    print("\n" + "=" * 64)
    print("1. SURVIVORS BY PERSISTENCE THRESHOLD")
    print("=" * 64)
    print(f"{'min_frames':>11} {'survivors':>10} {'removed':>9}   what it means")
    print("-" * 64)
    for m in (1, 2, 3, 5, 10, 20, 30, 60):
        kept = sum(1 for obs in tracks.values() if len(obs) >= m)
        note = ""
        if m == 1:
            note = "no filtering — every ID counts"
        elif m == 3:
            note = "2 seconds at 1.5 FPS on the Pi"
        elif m == 30:
            note = "1.25 s of clip time at 24 fps"
        print(f"{m:>11} {kept:>10} {len(tracks)-kept:>9}   {note}")

    # ── 2. Track length distribution ─────────────────────────────────
    lengths = sorted(len(o) for o in tracks.values())
    print("\n" + "=" * 64)
    print("2. HOW LONG DO TRACKS LIVE?")
    print("=" * 64)
    buckets = [(1, 1), (2, 2), (3, 5), (6, 10), (11, 30),
               (31, 100), (101, 10**9)]
    for lo, hi in buckets:
        n = sum(1 for L in lengths if lo <= L <= hi)
        share = 100 * n / len(lengths)
        label = f"{lo}" if lo == hi else (f"{lo}+" if hi > 10**8 else f"{lo}-{hi}")
        bar = "█" * int(share / 2)
        print(f"{label:>8} frames  {n:>5} tracks  {share:>5.1f}%  {bar}")

    print(f"\nmedian track length {statistics.median(lengths):.0f} frames"
          f"  ({statistics.median(lengths)/24:.1f} s)")

    # ── 3. Why are the short tracks short? ───────────────────────────
    print("\n" + "=" * 64)
    print(f"3. THE SHORT TRACKS (<= {SHORT_TRACK} frames) — REAL OR NOISE?")
    print("=" * 64)

    short = {t: o for t, o in tracks.items() if len(o) <= SHORT_TRACK}
    long_ = {t: o for t, o in tracks.items() if len(o) > SHORT_TRACK}

    if not short:
        print("None. Nothing for a persistence filter to remove.")
    else:
        def mean_conf(group):
            vals = [d["confidence"] for obs in group.values() for d in obs]
            return sum(vals) / len(vals) if vals else 0.0

        def at_edge(obs):
            """Does this track start or end near the image boundary?"""
            for d in (obs[0], obs[-1]):
                x1, y1, x2, y2 = d["bbox"]
                if (x1 < EDGE_MARGIN or y1 < EDGE_MARGIN
                        or x2 > FRAME_W - EDGE_MARGIN
                        or y2 > FRAME_H - EDGE_MARGIN):
                    return True
            return False

        edge = sum(1 for o in short.values() if at_edge(o))
        short_det = sum(len(o) for o in short.values())

        print(f"short tracks            {len(short)} of {len(tracks)} "
              f"({100*len(short)/len(tracks):.1f}%)")
        print(f"their detections        {short_det} of {len(dets)} "
              f"({100*short_det/len(dets):.1f}%)")
        print(f"mean confidence         {mean_conf(short):.3f}   "
              f"(long tracks: {mean_conf(long_):.3f})")
        print(f"starting/ending at edge {edge} of {len(short)} "
              f"({100*edge/len(short):.0f}%)")

        print("\nReading this:")
        conf_gap = mean_conf(long_) - mean_conf(short)
        if conf_gap > 0.08:
            print("  • Short tracks are notably LOWER confidence than long ones —")
            print("    consistent with flicker. Persistence filtering is the right fix.")
        else:
            print("  • Short tracks have SIMILAR confidence to long ones — so they are")
            print("    probably NOT false positives. Filtering them discards real people.")
        if edge / len(short) > 0.5:
            print("  • Most start or end at the frame boundary — these are people")
            print("    walking into or out of view, not detector errors.")
        else:
            print("  • Most appear mid-frame, not at the boundary — that points at")
            print("    flicker or ID switches rather than people entering/leaving.")

    # ── Recommendation ───────────────────────────────────────────────
    print("\n" + "=" * 64)
    print("WHAT TO DO")
    print("=" * 64)
    kept3 = sum(1 for o in tracks.values() if len(o) >= 3)
    print(f"min_frames=3 gives {kept3} survivors, down from {len(tracks)}.")
    print()
    print("If that is still far more people than the footage plausibly contains,")
    print("the excess is ID SWITCHES, not flicker — one person picking up several")
    print("IDs after occlusions. Persistence filtering cannot fix that. The options")
    print("are BoT-SORT (~30% slower, more robust to occlusion) or stating the")
    print("limitation openly.")
    print()
    print("Scrub the clip and count the people you can actually see in one frame.")
    print("Compare that to the numbers above. Your eyes are the ground truth here.")


if __name__ == "__main__":
    main()
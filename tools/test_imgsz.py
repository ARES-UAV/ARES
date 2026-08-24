#!/usr/bin/env python3
"""
Does running detection at a higher input size fix the tracking?

    python tools/test_imgsz.py

Re-tracks backend/data/demo_clip.mp4 at 640, 960 and 1280 and compares.

Why this matters: the model resizes every frame to `imgsz` before looking at
it. On a 1280-wide clip at imgsz=640, a 24-pixel person becomes a 12-pixel
person by the time the network sees them — below what it can resolve reliably.
Detections then flicker in and out, and no tracker can hold an identity across
detections that keep vanishing.

Doubling imgsz doubles the pixels the model has to work with. Inference gets
slower, which costs nothing here: this runs once, offline, to produce
detections.json. Nothing in the demo runs detection in real time.
"""

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLIP = REPO / "backend" / "data" / "demo_clip.mp4"
WEIGHTS = REPO / "models" / "yolov12s.pt"
OUT = REPO / "backend" / "data"

SIZES = [640, 960, 1280]
CONF, MAX_DET = 0.18, 1000


def run(imgsz: int) -> dict:
    from ultralytics import YOLO

    print(f"\n{'=' * 60}\nimgsz = {imgsz}\n{'=' * 60}")
    model = YOLO(str(WEIGHTS))
    model.model.names = {0: "person"}

    t0 = time.time()
    results = model.track(
        source=str(CLIP), tracker="bytetrack.yaml", persist=True,
        conf=CONF, max_det=MAX_DET, imgsz=imgsz, stream=True, verbose=False,
    )

    dets, ids = [], set()
    n_frames = 0
    for frame_id, r in enumerate(results):
        n_frames = frame_id + 1
        if r.boxes is None:
            continue
        for b in r.boxes:
            tid = int(b.id[0]) if b.id is not None else -1
            if tid != -1:
                ids.add(tid)
            dets.append({
                "frame_id": frame_id,
                "bbox": [round(v, 1) for v in b.xyxy[0].tolist()],
                "confidence": round(float(b.conf[0]), 3),
                "track_id": tid,
                "class": int(b.cls[0]),
            })

    elapsed = time.time() - t0
    path = OUT / f"detections_imgsz{imgsz}.json"
    path.write_text(json.dumps(dets, indent=2))

    lens = Counter(x["track_id"] for x in dets if x["track_id"] != -1)
    conf = [x["confidence"] for x in dets]
    alive = statistics.median(Counter(x["frame_id"] for x in dets).values())

    row = {
        "imgsz": imgsz,
        "dets": len(dets),
        "ids": len(ids),
        "median_track": statistics.median(lens.values()) if lens else 0,
        "median_conf": statistics.median(conf) if conf else 0,
        "conf70": 100 * sum(1 for c in conf if c > 0.7) / max(len(conf), 1),
        "per_frame": alive,
        "secs": elapsed,
    }

    print(f"  detections        {row['dets']}")
    print(f"  unique IDs        {row['ids']}")
    print(f"  median track len  {row['median_track']:.0f} frames")
    print(f"  median confidence {row['median_conf']:.3f}")
    print(f"  above 0.70 conf   {row['conf70']:.1f}%")
    print(f"  det per frame     {row['per_frame']:.0f}")
    print(f"  wall clock        {elapsed:.0f}s")
    return row


def main() -> None:
    if not CLIP.exists():
        sys.exit(f"No clip at {CLIP}")
    if not WEIGHTS.exists():
        sys.exit(f"No weights at {WEIGHTS}")

    rows = [run(s) for s in SIZES]

    print("\n" + "=" * 78)
    print(f"{'imgsz':>6} {'dets':>7} {'IDs':>6} {'track':>7} {'conf':>7} "
          f"{'>0.7':>7} {'/frame':>7} {'secs':>6}")
    print("-" * 78)
    for r in rows:
        print(f"{r['imgsz']:>6} {r['dets']:>7} {r['ids']:>6} "
              f"{r['median_track']:>7.0f} {r['median_conf']:>7.3f} "
              f"{r['conf70']:>6.1f}% {r['per_frame']:>7.0f} {r['secs']:>6.0f}")
    print("=" * 78)

    best = min(rows, key=lambda r: r["ids"])
    print(f"\nFewest unique IDs: imgsz={best['imgsz']} with {best['ids']}.")
    print("\nWhat to look for — all three should move together if size is the problem:")
    print("  • unique IDs DOWN        (fewer identities for the same people)")
    print("  • median track length UP (identities holding across more frames)")
    print("  • median confidence UP   (the model is surer about what it sees)")
    print("\nIf IDs barely move but confidence rises, size was not the limiting")
    print("factor and the tracker is the thing to change. If nothing moves, the")
    print("footage is simply too high for this model and the answer is a different")
    print("clip — not a parameter.")

    print(f"\nTo adopt:")
    print(f"  cp backend/data/detections_imgsz{best['imgsz']}.json "
          f"backend/data/detections.json")
    print(f"\nIf you adopt a size other than 640, record it — the detections were")
    print(f"produced at that resolution and the number belongs beside them.")


if __name__ == "__main__":
    main()
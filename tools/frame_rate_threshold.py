"""
At what frame rate does ByteTrack stop losing people?

    python tools/frame_rate_threshold.py

THE IDEA BEING TESTED
    ByteTrack fails at 4.8 FPS because the frame gap breaks IoU association.
    BoT-SORT survives the gap but fragments identities at every rate, so it
    needs a merge pass and it costs more (optical-flow GMC every frame).

    If a lighter detector ran fast enough, the gap would shrink and ByteTrack
    would work unmodified — cheaper tracker, no merge pass, no GMC.

    That plan needs a number before it needs a model: **how many FPS does
    ByteTrack actually require?** This sweeps the frame rate and finds out.

WHAT COMES OUT OF IT
    A latency budget. If ByteTrack recovers at 12 FPS, a detector must run in
    under 83 ms on the RB3; at 24 FPS, under 42 ms. Today YOLOv12s at 960
    takes 209.5 ms. The ratio between what is needed and what we have is the
    thing that says whether the lighter-model plan is reachable or wishful.

WHAT IT DOES NOT ANSWER
    Whether any particular model hits that budget on the Hexagon NPU. FLOPs do
    not predict NPU latency — this repo has already been wrong by 3x
    extrapolating from a GPU ratio. That needs an AI Hub run, not arithmetic.

    Nor does it account for the lighter model's lower per-frame recall. More
    frames of a worse detector is a different trade, and a real one.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend import config as C           # noqa: E402

CLIP = REPO_ROOT / "backend" / "data" / "demo_clip.mp4"
WEIGHTS = REPO_ROOT / "models" / "yolov12s.pt"
CFG_DIR = REPO_ROOT / "experiments" / "trackers"
OUT = REPO_ROOT / "experiments" / "frame_rate_threshold.json"
TOL_PX = 60.0

# stride -> effective FPS on a 24 FPS clip
STRIDES = [1, 2, 3, 4, 5]


def track(tracker: Path, stride: int) -> list:
    import cv2
    from ultralytics import YOLO
    model, recs, src = YOLO(str(WEIGHTS)), [], 0
    cap = cv2.VideoCapture(str(CLIP))
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if src % stride == 0:
            r = model.track(frame, persist=True, tracker=str(tracker),
                            conf=C.CONFIDENCE_THRESHOLD, imgsz=C.DETECTION_IMGSZ,
                            max_det=C.MAX_DETECTIONS_PER_FRAME, verbose=False)[0]
            if r.boxes is not None and len(r.boxes):
                xyxy = r.boxes.xyxy.cpu().numpy()
                ids = (r.boxes.id.cpu().numpy().astype(int)
                       if r.boxes.id is not None
                       else np.full(len(xyxy), -1, dtype=int))
                for b, t in zip(xyxy, ids):
                    recs.append({"f": src, "t": int(t),
                                 "c": ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)})
        src += 1
    cap.release()
    return recs


def confirmed(recs: list, fps: float) -> dict[int, dict[int, tuple]]:
    by: dict[int, dict[int, tuple]] = {}
    for r in recs:
        if r["t"] >= 0:
            by.setdefault(r["t"], {})[r["f"]] = r["c"]
    th = max(1, int(C.MIN_TRACK_SECONDS * fps))
    return {t: p for t, p in by.items() if len(p) >= th}


def score(ref: dict, cand: dict) -> dict:
    assigned, orphan = {}, 0
    for tc, pc in cand.items():
        best, bd = None, np.inf
        for tr, pr in ref.items():
            shared = set(pc) & set(pr)
            if not shared:
                continue
            d = float(np.median([np.hypot(pc[f][0] - pr[f][0], pc[f][1] - pr[f][1])
                                 for f in shared]))
            if d < bd:
                best, bd = tr, d
        if best is not None and bd <= TOL_PX:
            assigned[tc] = best
        else:
            orphan += 1
    hits = Counter(assigned.values())
    return {"reports": len(cand), "real_people": len(hits),
            "missed": len(ref) - len(hits),
            "duplicates": sum(n - 1 for n in hits.values() if n > 1),
            "orphans": orphan}


def main() -> None:
    bt = CFG_DIR / "bytetrack-default.yaml"

    print("reference: full rate, bytetrack-default ...", flush=True)
    ref_recs = track(bt, 1)
    ref = confirmed(ref_recs, C.CLIP_FPS)
    n_ref = len(ref)
    print(f"  {n_ref} confirmed at {C.CLIP_FPS} FPS\n")

    rows = []
    for stride in STRIDES:
        fps = C.CLIP_FPS / stride
        # stride 1 is the reference itself — no need to pay for it twice
        recs = ref_recs if stride == 1 else track(bt, stride)
        s = score(ref, confirmed(recs, fps))
        s.update(stride=stride, fps=round(fps, 1),
                 gap_frames=stride,
                 budget_ms=round(1000.0 / fps, 1),
                 min_track_frames=max(1, int(C.MIN_TRACK_SECONDS * fps)))
        rows.append(s)
        print(f"  stride {stride}  {fps:>4.1f} FPS  →  real {s['real_people']:>2}/{n_ref}"
              f"  missed {s['missed']:>2}  dup {s['duplicates']:>2}", flush=True)

    OUT.write_text(json.dumps({"reference_confirmed": n_ref,
                               "tolerance_px": TOL_PX,
                               "tracker": "bytetrack-default",
                               "rows": rows}, indent=2))

    print("\n" + "=" * 86)
    print(f"ByteTrack (shipped config) vs frame rate — reference {n_ref} survivors\n")
    print(f"{'FPS':>6}{'gap':>6}{'budget/frame':>15}{'reports':>9}{'real':>7}"
          f"{'missed':>8}{'dup':>6}")
    print("-" * 86)
    for r in rows:
        print(f"{r['fps']:>6}{r['gap_frames']:>6}{str(r['budget_ms']) + ' ms':>15}"
              f"{r['reports']:>9}{r['real_people']:>7}{r['missed']:>8}{r['duplicates']:>6}")
    print("=" * 86)

    ok = [r for r in rows if r["missed"] <= 1]
    if ok:
        slowest = min(ok, key=lambda r: r["fps"])
        have = 209.5   # RB3 Gen 2, YOLOv12s @ 960, measured median
        print(f"ByteTrack holds (<=1 missed) down to {slowest['fps']} FPS.")
        print(f"  → a detector must run in <= {slowest['budget_ms']} ms")
        print(f"  → YOLOv12s @ 960 on RB3 Gen 2 measures {have} ms")
        print(f"  → required speed-up: {have / slowest['budget_ms']:.1f}x")
    else:
        print("ByteTrack did not hold at any rate tested below full rate.")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

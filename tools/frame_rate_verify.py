"""
Is the recovered count the same PEOPLE, or just the same number?

    python tools/frame_rate_verify.py

WHY THIS EXISTS
    frame_rate_mitigation.py showed device-rate confirmed survivors going
    10 -> 20 with two ByteTrack parameter changes, against 21 at full rate.
    That is only good news if the 20 are the same twenty people the full-rate
    run found. Twenty unrelated tracks would print the same number.

    Track ids cannot answer it. ByteTrack numbers tracks in order of
    appearance, so id 7 in one run is not id 7 in the other. Confirmed
    survivors are matched by WHERE AND WHEN they were instead.

    BoT-SORT is included because its 47 needs explaining, not just excluding.
    If it is fragmenting identities, several of its confirmed tracks will
    match the SAME full-rate person — and that is measurable here, where the
    headline count alone would have called it the best result in the table.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend import config as C           # noqa: E402

CLIP = REPO_ROOT / "backend" / "data" / "demo_clip.mp4"
WEIGHTS = REPO_ROOT / "models" / "yolov12s.pt"
CFG_DIR = REPO_ROOT / "experiments" / "trackers"
OUT = REPO_ROOT / "experiments" / "frame_rate_verify.json"
TOL_PX = 60.0


def track(tracker: Path, stride: int) -> tuple[list, int]:
    import cv2
    from ultralytics import YOLO

    model, cap, recs, src, done = YOLO(str(WEIGHTS)), None, [], 0, 0
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
            done += 1
        src += 1
    cap.release()
    return recs, done


def confirmed_tracks(recs: list, fps: float) -> dict[int, dict[int, tuple]]:
    """Confirmed track -> {frame: centre}. Same 2.5 s rule, this run's rate."""
    by_track: dict[int, dict[int, tuple]] = {}
    for r in recs:
        if r["t"] >= 0:
            by_track.setdefault(r["t"], {})[r["f"]] = r["c"]
    threshold = max(1, int(C.MIN_TRACK_SECONDS * fps))
    return {t: pos for t, pos in by_track.items() if len(pos) >= threshold}


def pair(ref: dict, cand: dict) -> dict:
    """Greedy nearest-first pairing of candidate tracks onto reference tracks.

    Every candidate is allowed to claim its best reference match, INCLUDING one
    already claimed. That is deliberate: a second candidate landing on a
    reference person already matched is exactly what identity fragmentation
    looks like, and a one-to-one matcher would hide it by discarding the
    duplicate as "unmatched".
    """
    assigned, unmatched = {}, []
    for tc, pos_c in cand.items():
        best, best_d = None, np.inf
        for tr, pos_r in ref.items():
            shared = set(pos_c) & set(pos_r)
            if not shared:
                continue
            d = float(np.median([np.hypot(pos_c[f][0] - pos_r[f][0],
                                          pos_c[f][1] - pos_r[f][1]) for f in shared]))
            if d < best_d:
                best, best_d = tr, d
        if best is not None and best_d <= TOL_PX:
            assigned[tc] = best
        else:
            unmatched.append(tc)

    hits = Counter(assigned.values())
    return {
        "candidate_tracks": len(cand),
        "reference_tracks": len(ref),
        "reference_people_found": len(hits),
        "reference_people_missed": len(ref) - len(hits),
        "candidates_matching_nothing": len(unmatched),
        "duplicate_claims": sum(n - 1 for n in hits.values() if n > 1),
        "worst_fragmentation": max(hits.values()) if hits else 0,
    }


def main() -> None:
    stride = max(1, round(C.CLIP_FPS / C.DEVICE_FPS))
    device_fps = C.CLIP_FPS / stride

    print("reference: full rate, bytetrack-default ...", flush=True)
    ref_recs, _ = track(CFG_DIR / "bytetrack-default.yaml", 1)
    ref = confirmed_tracks(ref_recs, C.CLIP_FPS)
    print(f"  {len(ref)} confirmed survivors at {C.CLIP_FPS} FPS\n")

    out = {"tolerance_px": TOL_PX, "reference": {
        "tracker": "bytetrack-default", "fps": C.CLIP_FPS, "confirmed": len(ref)}, "candidates": []}

    for name in ("bytetrack-default", "bytetrack-wide", "botsort-gmc"):
        print(f"candidate: device rate, {name} ...", flush=True)
        recs, _ = track(CFG_DIR / f"{name}.yaml", stride)
        cand = confirmed_tracks(recs, device_fps)
        res = dict(pair(ref, cand), tracker=name, fps=round(device_fps, 1))
        out["candidates"].append(res)
        print(f"  {res['candidate_tracks']} confirmed → "
              f"{res['reference_people_found']} real people, "
              f"{res['duplicate_claims']} duplicate claims\n")

    OUT.write_text(json.dumps(out, indent=2))

    print("=" * 92)
    print(f"reference: {len(ref)} confirmed survivors at full rate\n")
    print(f"{'device-rate tracker':<22}{'confirmed':>11}{'real people':>13}"
          f"{'missed':>9}{'duplicates':>12}{'worst frag':>12}")
    print("-" * 92)
    for r in out["candidates"]:
        print(f"{r['tracker']:<22}{r['candidate_tracks']:>11}"
              f"{r['reference_people_found']:>13}{r['reference_people_missed']:>9}"
              f"{r['duplicate_claims']:>12}{r['worst_fragmentation']:>12}")
    print("=" * 92)
    print("confirmed  = what the dashboard would show")
    print("real people= distinct full-rate survivors actually accounted for")
    print("duplicates = extra confirmed tracks landing on a person already counted")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

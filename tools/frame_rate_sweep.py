"""
Can BoT-SORT be configured to stop fragmenting, before we write a merge pass?

    python tools/frame_rate_sweep.py

WHY BOT-SORT AND NOT BYTETRACK
    At 4.8 FPS the two trackers fail in opposite directions:

        ByteTrack   misses 12 of 21 people      — irrecoverable
        BoT-SORT    finds 20 of 21, reports 47  — recoverable

    A survivor the tracker never held cannot be recovered by any amount of
    post-processing. A survivor split across five ids is data you have,
    labelled wrong. Same asymmetry that put CONFIDENCE_THRESHOLD at 0.18.

    So BoT-SORT is the tracker, and the remaining job is the count.

WHAT THIS SWEEPS
    Fragmentation happens when a lost track is not re-matched before it dies,
    and a fresh id is spawned instead. Two parameters govern exactly that:

        track_buffer       frames a lost track stays alive for re-matching.
                           Higher = more chances to reclaim the same id.
        new_track_thresh   detection score needed to START a new identity.
                           Higher = fewer spurious new ids.

    The study used track_buffer 60 and the shipped 0.25 without tuning either.

THE MEASURE IS NOT THE COUNT
    Every row is scored against the full-rate reference BY POSITION:
    how many real people were found, how many missed, how many duplicate
    claims. A config that reports 21 while missing 8 and duplicating 8 is a
    failure, and the headline count cannot tell you that. This is the same
    check that caught `bytetrack-wide`.
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
OUT = REPO_ROOT / "experiments" / "frame_rate_sweep.json"
TOL_PX = 60.0

# baseline, then one axis at a time so a change can be attributed
GRID = [
    (60,  0.25),   # the study's config — the row to beat
    (150, 0.25),   # buffer alone
    (300, 0.25),   # buffer, harder
    (60,  0.50),   # threshold alone
    (150, 0.50),   # both
    (150, 0.70),   # threshold, harder
]


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
    """Duplicate claims are ALLOWED — that is how fragmentation is detected."""
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
    return {
        "reports": len(cand),
        "real_people": len(hits),
        "missed": len(ref) - len(hits),
        "duplicates": sum(n - 1 for n in hits.values() if n > 1),
        "worst_split": max(hits.values()) if hits else 0,
        "orphans": orphan,
    }


def main() -> None:
    from ultralytics.utils import ROOT as ULTRA_ROOT
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    base = yaml.safe_load((ULTRA_ROOT / "cfg" / "trackers" / "botsort.yaml").read_text())

    stride = max(1, round(C.CLIP_FPS / C.DEVICE_FPS))
    dev_fps = C.CLIP_FPS / stride

    print("reference: full rate, bytetrack-default ...", flush=True)
    ref = confirmed(track(CFG_DIR / "bytetrack-default.yaml", 1), C.CLIP_FPS)
    print(f"  {len(ref)} confirmed survivors at {C.CLIP_FPS} FPS\n")

    rows = []
    for buf, nt in GRID:
        name = f"botsort-b{buf}-n{nt}"
        cfg = dict(base, track_buffer=buf, new_track_thresh=nt,
                   match_thresh=0.95, gmc_method="sparseOptFlow", with_reid=False)
        p = CFG_DIR / f"{name}.yaml"
        p.write_text(yaml.safe_dump(cfg, sort_keys=False))

        print(f"  {name} ...", flush=True)
        s = score(ref, confirmed(track(p, stride), dev_fps))
        s.update(tracker=name, track_buffer=buf, new_track_thresh=nt)
        rows.append(s)
        print(f"    reports {s['reports']:>3} · real {s['real_people']:>2}/{len(ref)}"
              f" · missed {s['missed']:>2} · dup {s['duplicates']:>2}\n", flush=True)

    OUT.write_text(json.dumps({"reference_confirmed": len(ref),
                               "tolerance_px": TOL_PX, "rows": rows}, indent=2))

    print("=" * 94)
    print(f"reference: {len(ref)} confirmed survivors at full rate\n")
    print(f"{'config':<24}{'buf':>5}{'new_thr':>9}{'reports':>9}{'real':>7}"
          f"{'missed':>8}{'dup':>6}{'worst':>7}")
    print("-" * 94)
    for r in rows:
        print(f"{r['tracker']:<24}{r['track_buffer']:>5}{r['new_track_thresh']:>9}"
              f"{r['reports']:>9}{r['real_people']:>7}{r['missed']:>8}"
              f"{r['duplicates']:>6}{r['worst_split']:>7}")
    print("=" * 94)
    print("Pick on `real` first, then `dup`. A good `reports` with a bad `real`")
    print("is the bytetrack-wide failure and must not be selected.")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

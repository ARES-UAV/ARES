"""
Two questions the sweep left open.

    python tools/frame_rate_onebuild.py

Q1 — CAN ONE TRACKER SERVE BOTH RATES?
    The study measured ByteTrack at full rate and three trackers at device
    rate. It never measured BoT-SORT at FULL rate — so "use BoT-SORT for
    device work" quietly implied two configurations, one for each rate, and
    nobody checked whether that fork is necessary.

    If BoT-SORT b60-n0.5 also reaches ~21/21 at 24 FPS, there is no fork: one
    tracker, one config line, correct at both rates. That is worth more than a
    marginally better device-rate number, because a second configuration is a
    second thing to keep true.

Q2 — WHERE EXACTLY IS THE KNEE?
    The sweep jumped new_track_thresh 0.25 -> 0.50 and found duplicates fall
    17 -> 5 while real people fall 20 -> 19. Somewhere between those two
    values there may be a setting that keeps 20 people AND most of the
    duplicate reduction. The sweep's resolution was too coarse to see it.

Scored the same way throughout: against the full-rate ByteTrack reference, by
position, duplicates allowed. The headline count is never the criterion.
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
OUT = REPO_ROOT / "experiments" / "frame_rate_onebuild.json"
TOL_PX = 60.0
FINE = [0.30, 0.35, 0.40, 0.45]


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
            "worst_split": max(hits.values()) if hits else 0, "orphans": orphan}


def cfg_for(nt: float, name: str) -> Path:
    from ultralytics.utils import ROOT as ULTRA_ROOT
    base = yaml.safe_load((ULTRA_ROOT / "cfg" / "trackers" / "botsort.yaml").read_text())
    p = CFG_DIR / f"{name}.yaml"
    p.write_text(yaml.safe_dump(
        dict(base, track_buffer=60, new_track_thresh=nt, match_thresh=0.95,
             gmc_method="sparseOptFlow", with_reid=False), sort_keys=False))
    return p


def main() -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    stride = max(1, round(C.CLIP_FPS / C.DEVICE_FPS))
    dev_fps = C.CLIP_FPS / stride

    print("reference: full rate, bytetrack-default ...", flush=True)
    ref = confirmed(track(CFG_DIR / "bytetrack-default.yaml", 1), C.CLIP_FPS)
    print(f"  {len(ref)} confirmed at {C.CLIP_FPS} FPS\n")

    out = {"reference_confirmed": len(ref), "tolerance_px": TOL_PX,
           "full_rate": [], "device_rate": []}

    # Q1 — the same tracker at FULL rate. Does one config serve both?
    print("Q1  full rate, botsort-b60-n0.5 ...", flush=True)
    s = score(ref, confirmed(track(cfg_for(0.5, "botsort-b60-n0.5"), 1), C.CLIP_FPS))
    s.update(tracker="botsort-b60-n0.5", rate="full")
    out["full_rate"].append(s)
    print(f"    reports {s['reports']} · real {s['real_people']}/{len(ref)} · "
          f"missed {s['missed']} · dup {s['duplicates']}\n", flush=True)

    # Q2 — finer resolution across the knee.
    for nt in FINE:
        name = f"botsort-b60-n{nt}"
        print(f"Q2  device rate, new_track_thresh {nt} ...", flush=True)
        s = score(ref, confirmed(track(cfg_for(nt, name), stride), dev_fps))
        s.update(tracker=name, new_track_thresh=nt, rate="device")
        out["device_rate"].append(s)
        print(f"    reports {s['reports']} · real {s['real_people']}/{len(ref)} · "
              f"missed {s['missed']} · dup {s['duplicates']}\n", flush=True)

    OUT.write_text(json.dumps(out, indent=2))

    print("=" * 88)
    print(f"reference: {len(ref)} confirmed survivors, full rate, bytetrack-default\n")
    print("Q1 — one tracker at both rates?")
    for r in out["full_rate"]:
        print(f"   full rate  {r['tracker']:<20} reports {r['reports']:>3} · "
              f"real {r['real_people']:>2} · missed {r['missed']:>2} · dup {r['duplicates']:>2}")
    print("\nQ2 — the knee, at finer resolution")
    print(f"   {'new_track_thresh':<20}{'reports':>9}{'real':>7}{'missed':>8}{'dup':>6}{'worst':>7}")
    for r in out["device_rate"]:
        print(f"   {r['new_track_thresh']:<20}{r['reports']:>9}{r['real_people']:>7}"
              f"{r['missed']:>8}{r['duplicates']:>6}{r['worst_split']:>7}")
    print("=" * 88)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

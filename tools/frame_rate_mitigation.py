"""
The device-rate result was bad. Can a different tracker recover it?

    python tools/frame_rate_mitigation.py

WHAT THE FIRST STUDY FOUND
    At the device's measured 4.8 FPS the confirmed survivor count fell from
    21 to 10, and raw detections per frame fell from 22.6 to 8.8 — even though
    the device-rate run sees the SAME frames, just fewer of them.

    That second number is the tell. A detector is stateless; frame 0 is frame
    0 whether or not you also looked at frame 1. Detections per frame can only
    fall because `model.track()` does not return raw detections — it returns
    what the TRACKER accepted. ByteTrack's second association stage keeps
    low-confidence boxes only when they match an existing track, and our
    operating point (conf 0.18) leans on exactly those boxes.

    So one cause explains both halves: five times the frame gap means five
    times the pixel motion between looks, IoU between a box and its
    predecessor goes to zero, association fails, tracks die AND their
    low-confidence detections are discarded with them.

WHAT THIS SCRIPT TRIES
    Three trackers over the identical device-rate frames:

      bytetrack-default   what we ship — the baseline to beat
      bytetrack-wide      same tracker, permissive matching and a longer
                          buffer. Tests whether the gate is simply too tight.
      botsort-gmc         BoT-SORT with global motion compensation. GMC
                          estimates frame-to-frame camera movement and cancels
                          it before matching. A nadir camera on a moving
                          aircraft is the case it exists for, and at 4.8 FPS
                          the camera moves ~5 m between looks.

    Whichever wins, the honest report is the same: this is a tracker
    configuration finding, measured, not a claim that the problem is absent.
"""

from __future__ import annotations

import json
import sys
import time
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
OUT = REPO_ROOT / "experiments" / "frame_rate_mitigation.json"


def write_configs() -> dict[str, Path]:
    """Emit the tracker configs so the experiment is reproducible from the repo.

    Each config starts from ULTRALYTICS' OWN shipped yaml and overrides only
    the keys under test. Hand-writing a full config looked tidier and cost a
    run: BoT-SORT reads `model` even when `with_reid` is False, and a config
    missing one key fails at tracker construction, not at load.
    """
    from ultralytics.utils import ROOT as ULTRA_ROOT
    CFG_DIR.mkdir(parents=True, exist_ok=True)

    def shipped(name: str) -> dict:
        return yaml.safe_load((ULTRA_ROOT / "cfg" / "trackers" / f"{name}.yaml").read_text())

    bytetrack_default = shipped("bytetrack")

    # Two changes, each with a reason:
    #   match_thresh 0.8 -> 0.95   the gate is an IoU DISTANCE cap; at 4.8 FPS
    #                              consecutive boxes barely overlap, so a tight
    #                              cap rejects correct matches.
    #   track_buffer 30 -> 60      frames, not seconds. Keeps a lost track alive
    #                              long enough to be re-found across a gap.
    bytetrack_wide = dict(bytetrack_default, match_thresh=0.95, track_buffer=60)

    # BoT-SORT: same association family plus GMC. sparseOptFlow is the cheap
    # estimator and the one that matters here — it cancels the aircraft's own
    # motion before boxes are compared. Same two overrides as above so the
    # comparison isolates GMC rather than confounding it with the gate.
    botsort_gmc = dict(shipped("botsort"), match_thresh=0.95, track_buffer=60,
                       gmc_method="sparseOptFlow", with_reid=False)

    paths = {}
    for name, cfg in (("bytetrack-default", bytetrack_default),
                      ("bytetrack-wide", bytetrack_wide),
                      ("botsort-gmc", botsort_gmc)):
        p = CFG_DIR / f"{name}.yaml"
        p.write_text(yaml.safe_dump(cfg, sort_keys=False))
        paths[name] = p
    return paths


def run(tracker_path: Path, stride: int, label: str) -> dict:
    """Detect + track over every `stride`-th frame. Returns the summary."""
    import cv2
    from ultralytics import YOLO

    model = YOLO(str(WEIGHTS))
    cap = cv2.VideoCapture(str(CLIP))
    records, src, done, t0 = [], 0, 0, time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if src % stride == 0:
            r = model.track(frame, persist=True, tracker=str(tracker_path),
                            conf=C.CONFIDENCE_THRESHOLD, imgsz=C.DETECTION_IMGSZ,
                            max_det=C.MAX_DETECTIONS_PER_FRAME, verbose=False)[0]
            if r.boxes is not None and len(r.boxes):
                ids = (r.boxes.id.cpu().numpy().astype(int)
                       if r.boxes.id is not None
                       else np.full(len(r.boxes), -1, dtype=int))
                for tid in ids:
                    records.append({"frame_id": src, "track_id": int(tid)})
            done += 1
        src += 1
    cap.release()

    fps = C.CLIP_FPS / stride
    threshold = max(1, int(C.MIN_TRACK_SECONDS * fps))

    frames_by_track: dict[int, set] = {}
    for rec in records:
        if rec["track_id"] >= 0:
            frames_by_track.setdefault(rec["track_id"], set()).add(rec["frame_id"])
    confirmed = [t for t, f in frames_by_track.items() if len(f) >= threshold]

    return {
        "tracker": label,
        "stride": stride,
        "fps": round(fps, 1),
        "frames_processed": done,
        "raw_detections": len(records),
        "det_per_frame": round(len(records) / max(done, 1), 1),
        "track_ids": len(frames_by_track),
        "min_track_frames": threshold,
        "confirmed_survivors": len(confirmed),
        "wall_s": round(time.time() - t0, 1),
    }


def main() -> None:
    cfgs = write_configs()
    stride = max(1, round(C.CLIP_FPS / C.DEVICE_FPS))

    print(f"device rate: stride {stride} → {C.CLIP_FPS/stride:.1f} FPS · "
          f"persistence {max(1, int(C.MIN_TRACK_SECONDS * C.CLIP_FPS / stride))} frames\n")

    rows = []
    # Full-rate reference with the shipped tracker, so the table is self-contained.
    print("  full rate reference (bytetrack-default, stride 1) ...", flush=True)
    rows.append(dict(run(cfgs["bytetrack-default"], 1, "bytetrack-default"),
                     rate="full rate"))
    for name, path in cfgs.items():
        print(f"  device rate: {name} ...", flush=True)
        rows.append(dict(run(path, stride, name), rate="device rate"))

    OUT.write_text(json.dumps({"rows": rows}, indent=2))

    print("\n" + "=" * 82)
    print(f"{'rate':<12}{'tracker':<20}{'det/frame':>11}{'ids':>7}"
          f"{'confirmed':>11}{'wall s':>9}")
    print("-" * 82)
    for r in rows:
        print(f"{r['rate']:<12}{r['tracker']:<20}{r['det_per_frame']:>11}"
              f"{r['track_ids']:>7}{r['confirmed_survivors']:>11}{r['wall_s']:>9}")
    print("=" * 82)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

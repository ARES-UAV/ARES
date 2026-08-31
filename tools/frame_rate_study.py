"""
Does the survivor count survive the drop to the frame rate the hardware delivers?

    python tools/frame_rate_study.py
    python tools/frame_rate_study.py --limit 60      # quick check

THE QUESTION
    backend/data/detections.json was produced by running the model over EVERY
    frame of a 24 FPS clip. The device does not do that. On a Dragonwing RB3
    Gen 2 the model takes 209.5 ms, so it processes 4.8 frames per second — a
    little under one frame in five.

    Every number on the dashboard is downstream of tracking, and tracking is
    the part that should care: between two processed frames the aircraft has
    now travelled five times as far, so boxes jump five times as far, and
    ByteTrack matches boxes by how little they moved.

    If the confirmed survivor count changes, we need to know now and not on
    stage.

METHOD
    Run model.track() over the same clip twice, changing exactly one thing:

        full rate     every frame        24.0 FPS
        device rate   every 5th frame     4.8 FPS      = 24 / 4.8

    Same weights, same conf, same imgsz, same max_det, same tracker. Then
    apply the SAME persistence rule to both — imported from backend.tracks,
    not reimplemented — with the threshold recomputed from the same 2.5 second
    constant at each rate. That is the point of having written the rule in
    seconds: 60 frames at full rate, 12 at device rate, one rule.

WHY SKIPPING FRAMES IS THE RIGHT MODEL OF A SLOW DEVICE
    The device is not handed a slower video. It is handed the same flight and
    manages fewer looks at it. Dropping 4 frames in 5 is precisely what a
    processor that cannot keep up does.

    One consequence worth stating: ByteTrack's track_buffer is counted in
    FRAMES (30 by default), so at device rate a lost track is retained for
    6.2 seconds rather than 1.25. That is not a thumb on the scale — it is
    what the tracker would also do on the actual board, since it would be
    running at the same 4.8 FPS with the same default.

WHAT IS COMPARED
    Track IDs are NOT comparable between runs; ByteTrack numbers tracks in
    order of appearance, so "track 7" means different people in the two runs.
    Confirmed survivors are matched by WHERE AND WHEN they were, not by id.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend import config as C           # noqa: E402

CLIP = REPO_ROOT / "backend" / "data" / "demo_clip.mp4"
WEIGHTS = REPO_ROOT / "models" / "yolov12s.pt"
OUT_DIR = REPO_ROOT / "experiments"
RECORD = OUT_DIR / "frame_rate_study.json"
DOC = OUT_DIR / "FRAME_RATE_STUDY.md"


# ══════════════════════════════════════════════════════════════════════
#  Running the model
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Run:
    """One pass over the clip at one frame rate."""
    name: str
    stride: int
    fps: float
    records: list = field(default_factory=list)     # the data contract, verbatim
    wall_s: float = 0.0

    @property
    def min_track_frames(self) -> int:
        """The 2.5 s persistence rule, expressed in frames at THIS rate.

        Floored at 1 for the same reason backend.tracks floors it: a threshold
        of 0 would index the last element and confirm every track at the frame
        it was last seen.
        """
        return max(1, int(C.MIN_TRACK_SECONDS * self.fps))


def track_clip(stride: int, fps: float, name: str, limit: int | None) -> Run:
    """Run detection + ByteTrack over every `stride`-th frame of the clip.

    Frames are fed one at a time with persist=True rather than handing the
    whole video to track(), because that is the only way to skip frames: the
    video-level call has no notion of a device that cannot keep up.
    """
    import cv2
    from ultralytics import YOLO

    model = YOLO(str(WEIGHTS))
    cap = cv2.VideoCapture(str(CLIP))
    run = Run(name=name, stride=stride, fps=fps)

    t0 = time.time()
    src_frame = 0        # index in the ORIGINAL clip — keeps both runs on one timeline
    processed = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if src_frame % stride == 0:
            res = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=C.CONFIDENCE_THRESHOLD,
                imgsz=C.DETECTION_IMGSZ,
                max_det=C.MAX_DETECTIONS_PER_FRAME,
                verbose=False,
            )[0]

            if res.boxes is not None and len(res.boxes):
                xyxy = res.boxes.xyxy.cpu().numpy()
                confs = res.boxes.conf.cpu().numpy()
                ids = (res.boxes.id.cpu().numpy().astype(int)
                       if res.boxes.id is not None
                       else np.full(len(xyxy), -1, dtype=int))
                for box, cf, tid in zip(xyxy, confs, ids):
                    run.records.append({
                        "frame_id": int(src_frame),      # original-clip frame
                        "bbox": [round(float(v), 1) for v in box],
                        "confidence": round(float(cf), 2),
                        "track_id": int(tid),
                        "class": 0,
                    })
            processed += 1
            if processed % 25 == 0:
                print(f"    {name}: {processed} frames processed "
                      f"({time.time() - t0:.0f}s)", flush=True)
            if limit and processed >= limit:
                break
        src_frame += 1

    cap.release()
    run.wall_s = time.time() - t0
    return run


# ══════════════════════════════════════════════════════════════════════
#  Applying the persistence rule
# ══════════════════════════════════════════════════════════════════════

def confirm(run: Run) -> dict[int, int]:
    """track_id -> the frame it became a confirmed survivor on.

    Deliberately mirrors backend.tracks.confirmation_frames. It is reproduced
    here only because that function reads its threshold from module-level
    config, and this study needs two different thresholds in one process.
    The RULE is identical: distinct frames, threshold-th sighting.
    """
    frames_by_track: dict[int, set] = {}
    for r in run.records:
        if r["track_id"] < 0:
            continue
        frames_by_track.setdefault(r["track_id"], set()).add(r["frame_id"])

    threshold = run.min_track_frames
    out = {}
    for tid, frames in frames_by_track.items():
        if len(frames) >= threshold:
            out[tid] = sorted(frames)[threshold - 1]
    return out


def centroids(run: Run, tids) -> dict[int, dict[int, tuple]]:
    """For each track, its box centre on every frame it appears in."""
    out: dict[int, dict[int, tuple]] = {t: {} for t in tids}
    for r in run.records:
        t = r["track_id"]
        if t in out:
            x1, y1, x2, y2 = r["bbox"]
            out[t][r["frame_id"]] = ((x1 + x2) / 2, (y1 + y2) / 2)
    return out


def match(a: Run, b: Run, conf_a: dict, conf_b: dict, tol_px: float = 60.0):
    """Pair up confirmed survivors between two runs BY POSITION, not by id.

    WHY THIS IS NECESSARY
        ByteTrack numbers tracks in order of appearance. Skip four frames in
        five and the order changes, so id 7 in one run and id 7 in the other
        are different people. Comparing ids would produce a confident,
        meaningless answer.

    Two confirmed tracks match if they are ever seen on the same original
    frame within `tol_px`. Greedy, on the closest pair first — good enough to
    answer "did we lose anybody", which is the question.
    """
    ca, cb = centroids(a, conf_a), centroids(b, conf_b)
    pairs = []
    for ta, pos_a in ca.items():
        for tb, pos_b in cb.items():
            shared = set(pos_a) & set(pos_b)
            if not shared:
                continue
            d = np.median([float(np.hypot(pos_a[f][0] - pos_b[f][0],
                                          pos_a[f][1] - pos_b[f][1]))
                           for f in shared])
            if d <= tol_px:
                pairs.append((d, ta, tb, len(shared)))

    pairs.sort()
    used_a, used_b, matched = set(), set(), []
    for d, ta, tb, n in pairs:
        if ta in used_a or tb in used_b:
            continue
        used_a.add(ta); used_b.add(tb)
        matched.append({"a": ta, "b": tb, "median_px": round(d, 1), "shared_frames": n})

    return {
        "matched": matched,
        "only_in_a": sorted(set(conf_a) - used_a),
        "only_in_b": sorted(set(conf_b) - used_b),
    }


# ══════════════════════════════════════════════════════════════════════

def summarise(run: Run, conf: dict) -> dict:
    tids = {r["track_id"] for r in run.records if r["track_id"] >= 0}
    times = sorted(f / C.CLIP_FPS for f in conf.values())
    return {
        "name": run.name,
        "stride": run.stride,
        "fps": run.fps,
        "frames_processed": len({r["frame_id"] for r in run.records}),
        "raw_detections": len(run.records),
        "track_ids": len(tids),
        "min_track_frames": run.min_track_frames,
        "confirmed_survivors": len(conf),
        "first_confirm_s": round(times[0], 1) if times else None,
        "last_confirm_s": round(times[-1], 1) if times else None,
        "median_confirm_s": round(float(np.median(times)), 1) if times else None,
        "wall_s": round(run.wall_s, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N processed frames (smoke test)")
    ap.add_argument("--device-fps", type=float, default=None,
                    help="override; defaults to backend config DEVICE_FPS")
    args = ap.parse_args()

    device_fps = args.device_fps or C.DEVICE_FPS
    if not device_fps:
        sys.exit("DEVICE_FPS is None in backend/config.py — nothing to test against.")

    stride = max(1, round(C.CLIP_FPS / device_fps))
    effective = C.CLIP_FPS / stride

    print(f"clip {C.CLIP_FPS} FPS · device {device_fps} FPS "
          f"→ stride {stride} → effective {effective:.1f} FPS")
    print(f"persistence {C.MIN_TRACK_SECONDS}s = "
          f"{int(C.MIN_TRACK_SECONDS * C.CLIP_FPS)} frames at full rate, "
          f"{max(1, int(C.MIN_TRACK_SECONDS * effective))} at device rate\n")

    runs = [
        track_clip(1, C.CLIP_FPS, "full rate", args.limit),
        track_clip(stride, effective, "device rate", args.limit),
    ]
    confs = [confirm(r) for r in runs]
    summaries = [summarise(r, c) for r, c in zip(runs, confs)]

    m = match(runs[0], runs[1], confs[0], confs[1])

    import ultralytics
    result = {
        "question": "Does the confirmed survivor count survive the drop from "
                    "the clip's 24 FPS to the device's measured 4.8 FPS?",
        "clip": CLIP.name,
        "weights": WEIGHTS.name,
        "conf": C.CONFIDENCE_THRESHOLD,
        "imgsz": C.DETECTION_IMGSZ,
        "max_det": C.MAX_DETECTIONS_PER_FRAME,
        "tracker": "bytetrack.yaml",
        "ultralytics": ultralytics.__version__,
        "device": C.DEVICE_NAME,
        "device_fps": device_fps,
        "stride": stride,
        "persistence_s": C.MIN_TRACK_SECONDS,
        "runs": summaries,
        "matching": {
            "tolerance_px": 60.0,
            "matched": len(m["matched"]),
            "only_full_rate": len(m["only_in_a"]),
            "only_device_rate": len(m["only_in_b"]),
            "detail": m["matched"][:50],
        },
    }
    OUT_DIR.mkdir(exist_ok=True)
    RECORD.write_text(json.dumps(result, indent=2))

    # ── report ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    hdr = f"{'':22}" + "".join(f"{s['name']:>18}" for s in summaries)
    print(hdr)
    for key, label in (("fps", "effective FPS"),
                       ("frames_processed", "frames processed"),
                       ("raw_detections", "raw detections"),
                       ("track_ids", "track ids"),
                       ("min_track_frames", "persistence (frames)"),
                       ("confirmed_survivors", "CONFIRMED SURVIVORS"),
                       ("median_confirm_s", "median confirm (s)"),
                       ("last_confirm_s", "last confirm (s)")):
        print(f"{label:22}" + "".join(f"{str(s[key]):>18}" for s in summaries))
    print("=" * 70)
    print(f"matched by position : {len(m['matched'])}")
    print(f"only at full rate   : {len(m['only_in_a'])}   (lost by running slower)")
    print(f"only at device rate : {len(m['only_in_b'])}   (extra — likely id splits)")
    print(f"\nwrote {RECORD}")


if __name__ == "__main__":
    main()

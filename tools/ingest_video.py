#!/usr/bin/env python3
"""
Any video in, a working dashboard out. One command, no manual steps.

    python tools/ingest_video.py ~/Downloads/whatever_the_judge_gave_us.mp4

Writes into the repo:
    backend/data/demo_clip.mp4      re-encoded, browser-safe, CONSTANT frame rate
    backend/data/detections.json    real model output, the team JSON contract
    backend/data/clip_meta.json     this clip's geometry and rate — config reads it
    frontend/public/demo_clip.mp4   the copy the dashboard actually plays

Then: start the backend, start the frontend, and the dashboard is showing the
new clip. Nothing else to edit.

═══════════════════════════════════════════════════════════════════════
WHY THIS IS NOT JUST "RUN THE MODEL ON THE FILE"
═══════════════════════════════════════════════════════════════════════

Three things quietly break a dashboard fed a strange video, and all three are
handled here rather than left for demo day.

1. COORDINATE SPACE.  Ultralytics returns boxes in whatever pixel space you
   hand it. The dashboard's overlay scales boxes against FRAME_WIDTH /
   FRAME_HEIGHT, and `localize` turns pixel offsets into metres using the same
   width. Detect on a 3840-wide original, play a 1280-wide clip, and every box
   is wrong by 3x — silently, with no error anywhere.

   So detection runs on the RE-ENCODED file, never the original, and the
   geometry that came out of the re-encode is what gets written to config.
   `tools/build_demo_clip.py` learned this the hard way; the rule is the same.

2. VARIABLE FRAME RATE.  Phone cameras and screen recordings are usually VFR —
   the gap between frames changes as the encoder feels like it. The dashboard's
   whole clock is `frame_id / CLIP_FPS`, which assumes those are evenly spaced.
   Feed it VFR and the mission log drifts away from the video, slowly, in a way
   that looks like a bug in the log.

   So the re-encode forces constant frame rate. This is not optional.

3. RESOLUTION vs THE SIZE FLOOR.  This model degrades when a person spans much
   under ~24 px (CONVENTIONS.md, maximum operating altitude). Downscaling a 4K clip
   to 720p to "match the demo" can push every person under that floor and the
   run returns almost nothing.

   So native resolution is kept, capped only for sanity, and the summary
   reports the share of detections clearing 0.70 confidence, benchmarked
   against THE DEMO CLIP rather than against an absolute cut.

   That calibration matters and it cost a wrong version of this check. CONVENTIONS.md
   records ~32 % above 0.70 on "lower-altitude footage" and ~4 % on footage
   flown too high — but the 32 % is ground-level C2A imagery, a different
   domain. The demo clip, which is aerial and produces a working dashboard,
   sits at 5.5 %. Judging aerial footage against a ground-level reference
   condemns everything. The demo clip is the honest yardstick because it is the
   one we know works end to end.

═══════════════════════════════════════════════════════════════════════
WHAT IT DOES NOT DO
═══════════════════════════════════════════════════════════════════════

Localization is still nadir geometry against ASSUMED altitude, FOV and origin
(backend/config.py). A borrowed video has no telemetry, so the map pins are
positioned by an assumption, exactly as the demo clip's are. That assumption is
disclosed on the dashboard; ingesting a new video does not make it truer.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

WEIGHTS = REPO / "models" / "yolov12s.pt"
OUT_CLIP = REPO / "backend" / "data" / "demo_clip.mp4"
OUT_DETS = REPO / "backend" / "data" / "detections.json"
OUT_META = REPO / "backend" / "data" / "clip_meta.json"
PUBLIC = REPO / "frontend" / "public" / "demo_clip.mp4"

# Above this the model gets slower with nothing to show for it, and browsers
# start struggling to scrub. Aspect ratio is preserved; this is a cap, not a
# target — a 640x480 clip is left at 640x480.
MAX_WIDTH = 1920

# The demo clip's own figures, measured. Reference points for "is this footage
# workable", because this is the footage known to produce a working dashboard.
DEMO_PCT_070 = 5.5          # share of detections above 0.70 confidence
DEMO_MEDIAN_PX = 21.5       # median box height


def sh(cmd: list[str], what: str) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        sys.exit(f"FAILED: {what}")
    return r.stdout


def need(binary: str) -> None:
    if shutil.which(binary) is None:
        sys.exit(f"'{binary}' not found. Install ffmpeg:\n"
                 f"  macOS   brew install ffmpeg\n"
                 f"  Ubuntu  sudo apt install ffmpeg")


def probe(src: Path) -> dict:
    """Read the source's real geometry and frame rate.

    `avg_frame_rate` is used rather than `r_frame_rate`: r_frame_rate is the
    container's nominal tick rate and is often a wild number like 90000/1 on a
    VFR file, while avg_frame_rate is frames divided by duration, which is what
    a constant-rate re-encode should target.
    """
    out = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries",
              "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,codec_name",
              "-show_entries", "format=duration",
              "-of", "json", str(src)], "ffprobe")
    d = json.loads(out)
    if not d.get("streams"):
        sys.exit(f"No video stream found in {src.name}")
    s = d["streams"][0]

    num, _, den = s.get("avg_frame_rate", "0/0").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    if not (0 < fps < 240):
        num, _, den = s.get("r_frame_rate", "0/0").partition("/")
        fps = float(num) / float(den) if den and float(den) else 0.0
    if not (0 < fps < 240):
        fps = 25.0
        print("  ! frame rate unreadable — assuming 25 fps")

    return {
        "width": int(s["width"]), "height": int(s["height"]),
        "fps_src": round(fps, 4), "codec": s.get("codec_name", "?"),
        "duration_s": round(float(d.get("format", {}).get("duration") or 0), 2),
    }


def target_geometry(w: int, h: int, cap: int) -> tuple[int, int]:
    """Cap the width, preserve aspect, keep both dimensions even (h264 needs it)."""
    if w <= cap:
        return w - (w % 2), h - (h % 2)
    nh = round(h * cap / w)
    return cap - (cap % 2), nh - (nh % 2)


def reencode(src: Path, dst: Path, w: int, h: int, fps: float, seconds: float | None) -> None:
    """Re-encode to a constant-frame-rate, seekable, browser-safe mp4.

    -r before -i would drop frames on the way in; after -i it resamples on the
    way out, which is the CFR conversion we want. +faststart moves the index to
    the front so the browser can scrub without downloading the whole file, and
    yuv420p is the pixel format Safari will actually play.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-vf", f"scale={w}:{h}", "-r", f"{fps}",
            "-vsync", "cfr", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)]
    sh(cmd, "ffmpeg re-encode")


def detect(clip: Path, tracker: str, conf: float, imgsz: int, max_det: int) -> list[dict]:
    """Detect and track over the re-encoded clip. Emits the team JSON contract."""
    import cv2
    import numpy as np
    from ultralytics import YOLO

    if not WEIGHTS.exists():
        sys.exit(f"Weights not found: {WEIGHTS}\n"
                 f"Fetch them from the GitHub Release, or point WEIGHTS elsewhere.")

    model = YOLO(str(WEIGHTS))
    cap = cv2.VideoCapture(str(clip))
    records, frame_id = [], 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        r = model.track(frame, persist=True, tracker=tracker, conf=conf,
                        imgsz=imgsz, max_det=max_det, verbose=False)[0]
        if r.boxes is not None and len(r.boxes):
            xyxy = r.boxes.xyxy.cpu().numpy()
            cf = r.boxes.conf.cpu().numpy()
            ids = (r.boxes.id.cpu().numpy().astype(int)
                   if r.boxes.id is not None
                   else np.full(len(xyxy), -1, dtype=int))
            for b, c, t in zip(xyxy, cf, ids):
                records.append({
                    "frame_id": frame_id,
                    "bbox": [round(float(v), 1) for v in b],
                    "confidence": round(float(c), 2),
                    "track_id": int(t),
                    "class": 0,
                })
        frame_id += 1
        if frame_id % 50 == 0:
            print(f"    {frame_id} frames · {len(records)} detections", flush=True)

    cap.release()
    return records


def summarise(records: list[dict], fps: float, min_track_s: float) -> dict:
    """The numbers that say whether this clip will produce a sane dashboard."""
    import numpy as np

    frames = {r["frame_id"] for r in records}
    by_track: dict[int, set] = {}
    for r in records:
        if r["track_id"] >= 0:
            by_track.setdefault(r["track_id"], set()).add(r["frame_id"])

    threshold = max(1, int(min_track_s * fps))
    confirmed = [t for t, f in by_track.items() if len(f) >= threshold]
    heights = [r["bbox"][3] - r["bbox"][1] for r in records] or [0]
    confs = [r["confidence"] for r in records] or [0]

    return {
        "raw_detections": len(records),
        "frames_with_detections": len(frames),
        "track_ids": len(by_track),
        "min_track_frames": threshold,
        "confirmed_survivors": len(confirmed),
        "median_person_px": round(float(np.median(heights)), 1),
        # Share of detections clearing 0.70. Compared against DEMO_PCT_070
        # below, not an absolute cut — see the module docstring for why the
        # 32 % figure in CONVENTIONS.md is the wrong reference for aerial footage.
        "pct_above_070": round(100 * float(np.mean(np.array(confs) > 0.70)), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingest any video into the ARES dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("video", type=Path, help="any video file")
    ap.add_argument("--max-width", type=int, default=MAX_WIDTH,
                    help=f"cap output width, aspect preserved (default {MAX_WIDTH})")
    ap.add_argument("--seconds", type=float, default=None,
                    help="use only the first N seconds")
    ap.add_argument("--fps", type=float, default=None,
                    help="force output frame rate (default: the source's)")
    ap.add_argument("--tracker", default=None,
                    help="tracker yaml (default: backend config TRACKER)")
    args = ap.parse_args()

    need("ffmpeg"); need("ffprobe")
    src = args.video.expanduser()
    if not src.is_file():
        sys.exit(f"Not a file: {src}")

    from backend import config as C
    tracker = args.tracker or getattr(C, "TRACKER", "bytetrack.yaml")

    print(f"\n── source ──────────────────────────────────────────")
    info = probe(src)
    print(f"  {src.name}")
    print(f"  {info['width']}x{info['height']} · {info['fps_src']} fps · "
          f"{info['duration_s']}s · {info['codec']}")

    w, h = target_geometry(info["width"], info["height"], args.max_width)
    fps = args.fps or info["fps_src"]
    if (w, h) != (info["width"], info["height"]):
        print(f"  → capped to {w}x{h}")

    print(f"\n── re-encoding to constant {fps} fps ───────────────")
    reencode(src, OUT_CLIP, w, h, fps, args.seconds)
    real = probe(OUT_CLIP)
    print(f"  {OUT_CLIP.relative_to(REPO)} · {real['width']}x{real['height']} · "
          f"{real['fps_src']} fps · {real['duration_s']}s")

    print(f"\n── detecting · {tracker} · conf {C.CONFIDENCE_THRESHOLD} · "
          f"imgsz {C.DETECTION_IMGSZ} ──")
    records = detect(OUT_CLIP, tracker, C.CONFIDENCE_THRESHOLD,
                     C.DETECTION_IMGSZ, C.MAX_DETECTIONS_PER_FRAME)
    OUT_DETS.write_text(json.dumps(records))

    # The geometry config must use. Written from what the FILE actually is,
    # measured after the re-encode — not from what we asked ffmpeg for.
    meta = {
        "source": src.name,
        "width": real["width"], "height": real["height"],
        "fps": real["fps_src"], "duration_s": real["duration_s"],
        "tracker": tracker,
        "conf": C.CONFIDENCE_THRESHOLD, "imgsz": C.DETECTION_IMGSZ,
        "max_det": C.MAX_DETECTIONS_PER_FRAME,
    }
    stats = summarise(records, real["fps_src"], C.MIN_TRACK_SECONDS)
    meta.update(stats)
    OUT_META.write_text(json.dumps(meta, indent=2))

    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT_CLIP, PUBLIC)

    print(f"\n── result ──────────────────────────────────────────")
    print(f"  raw detections       {stats['raw_detections']:>8,}")
    print(f"  track ids issued     {stats['track_ids']:>8,}")
    print(f"  persistence          {stats['min_track_frames']:>8} frames "
          f"({C.MIN_TRACK_SECONDS}s at {real['fps_src']} fps)")
    print(f"  CONFIRMED SURVIVORS  {stats['confirmed_survivors']:>8}")
    print(f"  median person height {stats['median_person_px']:>8} px   (context only)")
    print(f"  above 0.70 conf      {stats['pct_above_070']:>7}%   "
          f"(demo clip: {DEMO_PCT_070}%)")

    print(f"\n── written ─────────────────────────────────────────")
    for p in (OUT_CLIP, OUT_DETS, OUT_META, PUBLIC):
        print(f"  {p.relative_to(REPO)}")

    # ── warnings, loudest last ────────────────────────────────────────
    warn = []
    if stats["pct_above_070"] < DEMO_PCT_070 * 0.5:
        warn.append(
            f"Only {stats['pct_above_070']}% of detections clear 0.70 confidence, "
            f"against {DEMO_PCT_070}% on the demo clip.\n"
            f"    Less than half the reference. The footage is probably flown "
            f"higher than the model handles, or\n"
            f"    --max-width shrank people below what it can resolve "
            f"(median box here: {stats['median_person_px']} px, "
            f"demo clip {DEMO_MEDIAN_PX} px).")
    if stats["confirmed_survivors"] == 0:
        warn.append("No track survived the persistence filter. The dashboard "
                    "will show zero survivors.")
    if real["duration_s"] < C.MIN_TRACK_SECONDS * 2:
        warn.append(f"Clip is {real['duration_s']}s and persistence needs "
                    f"{C.MIN_TRACK_SECONDS}s. Very little can confirm.")
    for w_ in warn:
        print(f"\n  ⚠  {w_}")

    print(f"\n  Start the dashboard:")
    print(f"    uvicorn backend.main:app --reload      # terminal 1")
    print(f"    cd frontend && npm run dev             # terminal 2\n")


if __name__ == "__main__":
    main()

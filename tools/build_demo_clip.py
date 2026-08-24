#!/usr/bin/env python3
"""
Turn a VisDrone-VID sequence into the demo clip + real detections.json.

    python tools/build_demo_clip.py ~/Downloads/VisDrone2019-VID-val uav0000086_00000_v

Writes into the repo:
    backend/data/demo_clip.mp4        13 s, 1280x720, 24 fps, faststart
    backend/data/detections.json      real model output, team JSON contract
    frontend/public/demo_clip.mp4     copy for the backend-off path
    models/test_frame_dense.jpg       busiest frame, for the Pi benchmark

THE RULE THAT MATTERS: detection runs on the ASSEMBLED 1280x720 clip, never
on the original JPEGs. Ultralytics returns boxes in whatever coordinate space
you feed it. VisDrone frames are usually 1344x756 or 1920x1080 — run on those
and every box is wrong by that ratio against FRAME_WIDTH=1280, silently.
"""

import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

WEIGHTS   = REPO / "models" / "yolov12s.pt"
CLIP      = REPO / "backend" / "data" / "demo_clip.mp4"
DETS      = REPO / "backend" / "data" / "detections.json"
PUBLIC    = REPO / "frontend" / "public" / "demo_clip.mp4"
DENSE     = REPO / "models" / "test_frame_dense.jpg"

WIDTH, HEIGHT, FPS, SECONDS = 1280, 720, 24, 13
CONF, MAX_DET = 0.18, 1000


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-2000:], file=sys.stderr)
        sys.exit(f"FAILED: {' '.join(cmd[:3])} ...")
    return result.stdout


def find_sequence(given: Path, name: str) -> Path:
    given = given.expanduser()
    for candidate in [given / "sequences" / name, *given.rglob(f"sequences/{name}")]:
        if candidate.is_dir():
            return candidate
    sys.exit(f"Sequence '{name}' not found under {given}")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    seq = find_sequence(Path(sys.argv[1]), sys.argv[2])
    frames = sorted(seq.glob("*.jpg"))
    print(f"sequence: {seq}\nframes:   {len(frames)}")
    if len(frames) < FPS * SECONDS:
        print(f"  ! only {len(frames)} frames — clip will be shorter than {SECONDS}s")

    CLIP.parent.mkdir(parents=True, exist_ok=True)
    DENSE.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. Assemble ──────────────────────────────────────────────────
    # glob pattern rather than %07d — VisDrone frame naming varies and
    # these sort correctly lexicographically either way.
    print("\n[1/5] assembling clip …")
    run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-pattern_type", "glob", "-i", str(seq / "*.jpg"),
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
               f"crop={WIDTH}:{HEIGHT}",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-t", str(SECONDS), str(CLIP),
    ])

    # ── 2. Verify dimensions — the trap this whole script exists to avoid
    print("[2/5] verifying …")
    probe = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", str(CLIP),
    ]).strip()
    w, h = (int(v) for v in probe.split(","))
    print(f"      {w}x{h}")
    if (w, h) != (WIDTH, HEIGHT):
        sys.exit(f"  ! expected {WIDTH}x{HEIGHT} — every coordinate would be wrong. Stopping.")

    # ── 3. Detect + track ────────────────────────────────────────────
    print("[3/5] detecting and tracking (this takes a minute) …")
    from ultralytics import YOLO

    if not WEIGHTS.exists():
        sys.exit(f"No weights at {WEIGHTS} — download them from Drive first")

    model = YOLO(str(WEIGHTS))
    model.model.names = {0: "person"}      # YOLOv12s ships as 'human'

    results = model.track(
        source=str(CLIP),
        tracker="bytetrack.yaml",   # explicit — 8.4.x defaults to tracktrack
        persist=True,
        conf=CONF,
        max_det=MAX_DET,
        stream=True,                # frame by frame, or RAM explodes
        save=True,                  # annotated copy, useful for the demo video
        verbose=False,
    )

    detections, track_ids = [], set()
    n_frames = 0

    for frame_id, r in enumerate(results):
        n_frames = frame_id + 1
        if r.boxes is None:
            continue
        for b in r.boxes:
            tid = int(b.id[0]) if b.id is not None else -1
            if tid != -1:
                track_ids.add(tid)
            detections.append({
                "frame_id":   frame_id,
                "bbox":       [round(v, 1) for v in b.xyxy[0].tolist()],
                "confidence": round(float(b.conf[0]), 3),
                "track_id":   tid,
                "class":      int(b.cls[0]),
            })

    DETS.write_text(json.dumps(detections, indent=2))

    # ── 4. Busiest frame, for an honest Pi benchmark ─────────────────
    print("[4/5] extracting densest frame …")
    busiest, count = Counter(d["frame_id"] for d in detections).most_common(1)[0]
    run([
        "ffmpeg", "-y", "-i", str(CLIP),
        "-vf", f"select=eq(n\\,{busiest})", "-vframes", "1",
        "-q:v", "2", str(DENSE),
    ])

    # ── 5. Copy for the backend-off path ─────────────────────────────
    print("[5/5] copying to frontend/public …")
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(CLIP, PUBLIC)

    # ── Summary ──────────────────────────────────────────────────────
    untracked = sum(1 for d in detections if d["track_id"] == -1)
    print("\n" + "=" * 58)
    print(f"frames              {n_frames}")
    print(f"raw detections      {len(detections)}")
    print(f"unique track IDs    {len(track_ids)}")
    print(f"untracked (-1)      {untracked}")
    print(f"densest frame       {busiest} with {count} detections")
    print("=" * 58)
    print(f"\n  {CLIP.relative_to(REPO)}")
    print(f"  {DETS.relative_to(REPO)}")
    print(f"  {DENSE.relative_to(REPO)}")

    print("\nEXPECT THE TRACK COUNT TO LOOK TOO HIGH.")
    print("At conf 0.18 on real footage you get flicker — a shadow or a bag that")
    print("reads person-shaped for one frame gets a fresh ID. That is the price of")
    print("the high-recall threshold, and it is what Robin's persistence filter")
    print("removes. Write the number down: the before/after is a good demo.")

    print("\nNext:")
    print("  1. point backend/config.py at detections.json (not fixture_detections.json)")
    print("  2. git rm --cached backend/data/fixture_detections.json && rm it")
    print("  3. restart the backend, reload the dashboard")


if __name__ == "__main__":
    main()
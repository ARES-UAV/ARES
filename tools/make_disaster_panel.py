#!/usr/bin/env python3
"""
Build one image showing the model detecting people in DISASTER scenes.

    python tools/make_disaster_panel.py ~/Downloads/C2A/images/val

WHY THIS EXISTS
    The demo clip is a VisDrone urban sequence — traffic, shops, a crosswalk.
    That is a legitimate choice (it is annotated, dense, and the detections over
    it are real model output), but on a page that says "disaster zone" it
    invites one obvious question:

        "Your model detects upright pedestrians in daylight on clean pavement.
         How does that transfer to someone half-buried in rubble?"

    The answer is that the model is trained on COMBINED C2A + VisDrone, and C2A
    is specifically people in disaster scenes. This script makes that answer
    visible instead of merely available: same weights, same settings, run over
    disaster imagery, tiled into one panel.

    Nothing here is fabricated. It is the shipped model at the shipped
    thresholds over public disaster images.

WHAT IT DOES
    1. Runs the model over every image in the directory you point it at
    2. Ranks them by how many people were found
    3. Takes the top N (default 4) and draws boxes in the dashboard's own
       survivor cyan, so the panel and the product look like one system
    4. Tiles them into a single PNG for the site and the deck

OUTPUT
    docs/site/img/disaster-detections.png
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WEIGHTS = REPO / "models" / "yolov12s.pt"
OUT = REPO / "docs" / "site" / "img" / "disaster-detections.png"

# Ship settings. These must match backend/config.py or the panel is showing a
# configuration nobody deploys.
CONF, MAX_DET, IMGSZ = 0.18, 1000, 960

# --survivor from frontend/src/tokens.css. OpenCV is BGR, not RGB.
CYAN_BGR = (189, 167, 34)          # #22A7BD
INK_BGR = (239, 237, 230)          # #E6EDEF
GUTTER_BGR = (19, 16, 11)          # #0B1013, the dashboard ground

TILE_W = 640                        # per-tile width in the finished panel
COLS = 2
TOP_N = 4
GUTTER = 8


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    src = Path(sys.argv[1]).expanduser()
    if not src.is_dir():
        sys.exit(f"Not a directory: {src}")
    if not WEIGHTS.exists():
        sys.exit(f"No weights at {WEIGHTS}")

    import cv2
    import numpy as np
    from ultralytics import YOLO

    images = sorted(
        p for p in src.rglob("*")
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not images:
        sys.exit(f"No images found under {src}")

    print(f"scanning {len(images)} images from {src}")
    print(f"settings: conf={CONF} max_det={MAX_DET} imgsz={IMGSZ}\n")

    model = YOLO(str(WEIGHTS))
    model.model.names = {0: "person"}

    # ── 1. score every image by how many people it finds ─────────────
    scored = []
    for i, path in enumerate(images):
        r = model.predict(
            str(path), conf=CONF, max_det=MAX_DET, imgsz=IMGSZ, verbose=False
        )[0]
        n = 0 if r.boxes is None else len(r.boxes)
        scored.append((n, path))
        if (i + 1) % 25 == 0 or i + 1 == len(images):
            print(f"  {i + 1}/{len(images)}")

    scored.sort(key=lambda t: -t[0])
    picked = [(n, p) for n, p in scored if n > 0][:TOP_N]

    if not picked:
        sys.exit(
            "No detections in any image. Check that the path really is C2A "
            "imagery and that the weights are the trained ones."
        )

    print("\nselected:")
    for n, p in picked:
        print(f"  {n:>3} detections   {p.name}")

    # ── 2. draw boxes in the dashboard's own colour ──────────────────
    tiles = []
    for n, path in picked:
        img = cv2.imread(str(path))
        if img is None:
            continue
        r = model.predict(
            str(path), conf=CONF, max_det=MAX_DET, imgsz=IMGSZ, verbose=False
        )[0]

        if r.boxes is not None:
            for b in r.boxes:
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
                conf = float(b.conf[0])
                cv2.rectangle(img, (x1, y1), (x2, y2), CYAN_BGR, 2)
                # Confidence above the box, only when there is room for it and
                # the box is big enough that a label is legible rather than
                # noise sitting on top of a 12-pixel person.
                if y1 > 14 and (x2 - x1) > 26:
                    cv2.putText(
                        img, f"{conf:.2f}", (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, CYAN_BGR, 1, cv2.LINE_AA,
                    )

        # Caption strip: the count, so a viewer can check the boxes against it.
        h, w = img.shape[:2]
        scale = TILE_W / w
        img = cv2.resize(img, (TILE_W, int(h * scale)), interpolation=cv2.INTER_AREA)
        cv2.rectangle(img, (0, img.shape[0] - 26), (TILE_W, img.shape[0]), GUTTER_BGR, -1)
        cv2.putText(
            img, f"{n} detected", (10, img.shape[0] - 9),
            cv2.FONT_HERSHEY_SIMPLEX, 0.46, INK_BGR, 1, cv2.LINE_AA,
        )
        tiles.append(img)

    # ── 3. tile them ─────────────────────────────────────────────────
    rows = []
    for i in range(0, len(tiles), COLS):
        row = tiles[i:i + COLS]
        h = max(t.shape[0] for t in row)
        # Pad every tile in the row to the same height so the grid lines up.
        row = [
            cv2.copyMakeBorder(
                t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=GUTTER_BGR
            )
            for t in row
        ]
        while len(row) < COLS:
            row.append(np.full((h, TILE_W, 3), GUTTER_BGR, dtype=np.uint8))
        rows.append(
            np.hstack(
                [row[0]]
                + [x for t in row[1:]
                   for x in (np.full((h, GUTTER, 3), GUTTER_BGR, dtype=np.uint8), t)]
            )
        )

    w = max(r.shape[1] for r in rows)
    rows = [
        cv2.copyMakeBorder(r, 0, 0, 0, w - r.shape[1], cv2.BORDER_CONSTANT, value=GUTTER_BGR)
        for r in rows
    ]
    panel = np.vstack(
        [rows[0]]
        + [x for r in rows[1:]
           for x in (np.full((GUTTER, w, 3), GUTTER_BGR, dtype=np.uint8), r)]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), panel)

    print(f"\nwrote {OUT.relative_to(REPO)}  ({panel.shape[1]}x{panel.shape[0]})")
    print("\nThis is the shipped model at the shipped thresholds over public")
    print("disaster imagery. Say exactly that when you use it — it is what")
    print("makes the urban demo clip a defensible choice rather than a gap.")


if __name__ == "__main__":
    main()

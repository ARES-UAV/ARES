"""Tunable constants for the ARES dashboard backend.

Everything a judge is likely to ask "where does that number come from?" about
lives here, not scattered through the code. Nothing in this file is derived at
runtime — the prototype has no live telemetry, so altitude, FOV and the GPS
origin are fixed per demo clip.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"

# Development scaffolding, NOT demo data — see the demo footage policy in
# CLAUDE.md. Delete this file once real model detections exist.
FIXTURE_PATH: Path = DATA_DIR / "fixture_detections.json"

# ── Detection ──────────────────────────────────────────────────────
# Deliberately low: a false alarm costs a rescuer seconds, a missed
# survivor cannot be recovered. Surfaced on the dashboard as
# "Detection Mode: High Recall".
CONFIDENCE_THRESHOLD: float = 0.18
MAX_DETECTIONS_PER_FRAME: int = 1000

# ── Clip geometry (fixed constants per demo clip) ──────────────────
FRAME_WIDTH: int = 1280
FRAME_HEIGHT: int = 720
CLIP_FPS: float = 30.0

ALTITUDE_M: float = 40.0          # stated maximum operating altitude
CAMERA_FOV_DEG: float = 60.0      # nadir-pointing
ORIGIN_LAT: float = 28.6139       # demo clip GPS origin
ORIGIN_LON: float = 77.2090

# ── Priority scoring weights ───────────────────────────────────────
# A transparent weighted formula, not a learned model — a judge will ask.
WEIGHT_CONFIDENCE: float = 0.4
WEIGHT_CLUSTER_SIZE: float = 0.3
WEIGHT_HAZARD_PROXIMITY: float = 0.3

# ── Dev server ─────────────────────────────────────────────────────
# Vite's default dev origins, for CORS.
CORS_ORIGINS: list = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

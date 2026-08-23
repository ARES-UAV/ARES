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
CLIP_FPS: float = 24.0

ALTITUDE_M: float = 20.0          # stated maximum operating altitude
CAMERA_FOV_DEG: float = 60.0      # nadir-pointing
ORIGIN_LAT: float = 26.1445       # demo clip GPS origin, at frame 0
ORIGIN_LON: float = 91.7362

# ── Flight track (assumed constant velocity) ───────────────────────
# The drone does not hover. At 20 m altitude and 60 deg FOV the camera sees
# about 23 m of ground, so a stationary origin puts every survivor in the clip
# inside one 23 m square regardless of how long the drone flew — which is not
# what a search flight looks like and makes the map unreadable.
#
# There is no telemetry to read a real track from, so one is assumed: a
# straight line at constant speed and heading from (ORIGIN_LAT, ORIGIN_LON) at
# frame 0. This is the same class of disclosed assumption as ALTITUDE_M and
# CAMERA_FOV_DEG — a fixed per-clip constant standing in for a measurement the
# prototype cannot make — and the pitch states it rather than hiding it.
#
# Heading is a compass bearing in degrees: 0 = north, 90 = east, clockwise.
DRONE_SPEED_MS: float = 5.0       # ground speed along the track
DRONE_HEADING_DEG: float = 45.0   # north-east

# ── Priority scoring ───────────────────────────────────────────────
# A transparent weighted formula, not a learned model — a judge will ask, and
# "a neural network decides" is a bad answer. One sentence covers it:
#
#   A survivor's priority is a weighted average of how confident the detector
#   is, how many other survivors are within CLUSTER_RADIUS_M of them, and how
#   close the nearest known hazard is.
#
# The three weights are relative, not absolute — `backend.priority` divides by
# whatever they sum to, so they do not have to add up to 1 and dropping a term
# does not shrink everyone's score. They are equal-ish on purpose: no term has
# earned the right to dominate the other two on evidence yet.
WEIGHT_CONFIDENCE: float = 0.4
WEIGHT_CLUSTER_SIZE: float = 0.3
WEIGHT_HAZARD_PROXIMITY: float = 0.3

# How close two survivors have to be to count as the same cluster. A group is
# a harder, slower extraction than the same number of people spread out, so it
# ranks higher. 15 m is a little under the ~23 m the camera sees at 20 m
# altitude — wide enough to join a group standing together, tight enough not to
# declare the whole frame one cluster.
CLUSTER_RADIUS_M: float = 15.0

# Neighbours at which the cluster term saturates at 1.0. Beyond this the
# distinction stops being useful: five together and nine together are both
# "a crowd", and without a ceiling one large group would flatten every other
# survivor's cluster score to nearly nothing.
CLUSTER_SATURATION: int = 4

# Known hazard positions as (latitude, longitude).
#
# EMPTY ON PURPOSE, and it must stay empty until the hazard classifier produces
# real output — hazard classification is Phase 2 (CLAUDE.md, Scope). Inventing
# a fire here to make the map look busy is the same failure as hand-authoring
# detections: one question from a judge exposes it.
#
# While this list is empty `backend.priority` drops the hazard term and
# renormalises the other two, and the dashboard says the term is inactive.
HAZARDS: list = []

# Distance at which a hazard stops contributing. At the hazard itself the term
# is 1.0, falling linearly to 0.0 here.
HAZARD_INFLUENCE_M: float = 50.0

# Band thresholds for the dashboard's status ramp. Below the first threshold is
# "warning" — there is deliberately no "clear" band, because the
# lowest-priority person in a disaster zone still needs rescuing and a green
# survivor row would say otherwise.
PRIORITY_SERIOUS_AT: float = 0.45
PRIORITY_CRITICAL_AT: float = 0.70

# ── Dev server ─────────────────────────────────────────────────────
# Vite's default dev origins, for CORS.
CORS_ORIGINS: list = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

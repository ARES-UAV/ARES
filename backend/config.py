"""Tunable constants for the ARES dashboard backend.

Everything a judge is likely to ask "where does that number come from?" about
lives here, not scattered through the code. Nothing in this file is derived at
runtime — the prototype has no live telemetry, so altitude, FOV and the GPS
origin are fixed per demo clip.
"""

from pathlib import Path
from typing import List, Optional, Tuple

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"

# Development scaffolding, NOT demo data — see the demo footage policy in
# CLAUDE.md. Delete this file once real model detections exist.
FIXTURE_PATH: Path = DATA_DIR / "fixture_detections.json"

# Cached OpenStreetMap tiles, served by `GET /tiles/{z}/{x}/{y}.png`.
#
# Demo-day constraint 3 in CLAUDE.md: tiles need internet and venue wifi
# fails. `tools/fetch_tiles.py` fills this directory from the ORIGIN_LAT /
# ORIGIN_LON below, so moving the origin and re-running moves the bundle.
# Untracked — tiles are downloaded, not committed.
TILES_DIR: Path = DATA_DIR / "tiles"

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
ORIGIN_LAT: float = 26.405892      # demo clip GPS origin, at frame 0
ORIGIN_LON: float = 92.233479

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
HAZARDS: List[Tuple[float, float]] = []

# Distance at which a hazard stops contributing. At the hazard itself the term
# is 1.0, falling linearly to 0.0 here.
HAZARD_INFLUENCE_M: float = 50.0

# Band thresholds for the dashboard's priority ramp.
#
# Four bands, and they are the QUARTERS of the score range. That is the whole
# rule: the score is 0-1, so the bands are 0.25 / 0.50 / 0.75. A judge asking
# "why 0.75?" gets an answer in one sentence, which no hand-tuned number was
# ever going to give. They are deliberately NOT fitted to the current fixture's
# score distribution — thresholds chosen to make a demo look colourful are the
# same failure as hand-authoring detections.
#
# The lowest band is "low", not "clear", and the dashboard renders it in a pale
# alarm colour rather than a green: the lowest-priority person in a disaster
# zone still needs rescuing, and a green survivor row would tell an operator
# otherwise.
PRIORITY_MEDIUM_AT: float = 0.25
PRIORITY_HIGH_AT: float = 0.50
PRIORITY_CRITICAL_AT: float = 0.75

# ── Mission event log ──────────────────────────────────────────────
# How often the priority of every known survivor is re-evaluated for the
# dashboard's event log, in seconds of playback.
#
# This is a SAMPLING RATE, not a smoothing fudge. Priority is a weighted
# average whose confidence term is the confidence of each track's latest
# detection, and that figure jitters frame to frame. Re-scoring on every frame
# of the development fixture emits 277 band changes — tracks flickering across
# the 0.75 cut on detector noise alone, which buries the events that carry
# information under events that carry none.
#
# Sampling once a second cuts that to 19 without hiding anything the log
# claims to show: a band change is reported when the re-evaluated band differs
# from the last one REPORTED, so a flicker that lands back where it started
# between samples is genuinely not a change in the dashboard's assessment.
# What the log does not show is that the score wandered across the threshold
# in between, and the panel says so on screen rather than implying the ranking
# was steady.
#
# `backend.events` additionally forces a re-evaluation on any frame that
# acquires a new track — that is the one thing which provably changes every
# other survivor's cluster term — and on the clip's final frame, so the log's
# closing bands are the same values `/api/survivors` hands the table.
EVENT_SAMPLE_INTERVAL_S: float = 1.0

# ── On-device benchmark ────────────────────────────────────────────
# Inference throughput measured on the target device, not on a laptop.
#
# `None` means exactly that: nobody has run the benchmark yet. The dashboard
# renders a dash and the words "not yet measured" rather than a number, and
# the mission-parameters panel tags the row accordingly instead of calling it
# measured. An invented FPS figure is the same failure as a hand-authored
# detection, and this is the one number a judge is most likely to press on —
# a Raspberry Pi 4 running a YOLO model is exactly where a prototype is
# expected to be slow.
#
# Set this to the real figure once `ai/` produces one. The panel picks it up
# with no frontend edit and re-tags the row "measured".
DEVICE_FPS: Optional[float] = None
DEVICE_NAME: str = "Raspberry Pi 4 Model B"

# ── Dev server ─────────────────────────────────────────────────────
# Vite's default dev origins, for CORS.
CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

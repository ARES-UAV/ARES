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

# The clip's detection records: real YOLOv12s output over the demo clip,
# produced offline by `tools/build_demo_clip.py` and replayed against the
# playback clock (CLAUDE.md, demo-day constraint 1). Not the hand-generated
# development fixture this pointed at while the frontend was being built.
DETECTIONS_PATH: Path = DATA_DIR / "detections.json"

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

# The input size the detections in DETECTIONS_PATH were produced at — the
# square the model resizes each frame to before it looks at it.
#
# Not a free-floating setting: change it and this constant stops describing the
# file, which is why the dashboard prints it. On a 1280-wide clip at 640 a
# 24-pixel person reaches the network as 12 pixels, below what it resolves
# reliably, and detections flicker in and out — no tracker holds an identity
# across boxes that keep vanishing.
#
# Chosen from a sweep over the same clip (`tools/test_imgsz.py`), which is why
# the dashboard tags it "chosen" rather than assumed or measured — it is a
# decision made on evidence, not a stand-in for a measurement the prototype
# cannot make:
#
#     imgsz    detections    unique track IDs
#       640          5502                 350
#       960          7081                 333
#      1280          7050                 345
#
# 960 finds the most and fragments them into the fewest identities; 1280 costs
# more inference for slightly worse tracking. Inference speed does not enter
# the choice — this runs once, offline, to produce the detections file, and
# nothing in the demo detects in real time. DEVICE_FPS is the figure that
# answers the on-device question, and it is separate.
DETECTION_IMGSZ: int = 960

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

# ── Track persistence (survivor confirmation) ──────────────────────
# How long a track has to persist before it counts as a confirmed survivor.
#
# CONFIDENCE_THRESHOLD is deliberately low, and this is the other half of that
# choice. At 0.18 the detector reports things that are person-shaped for a
# moment — a shadow, a bag, a patch of rubble — and the tracker duly gives each
# one an ID. On the current clip that is the difference between 333 unique
# track IDs and roughly 23 people: `tools/analyse_tracks.py` measures the short
# tracks at mean confidence 0.42 against 0.52 for the long ones, and finds only
# 7% of them starting or ending at the frame edge. Low confidence, mid-frame,
# gone in a frame or two is flicker, not a person walking out of shot — so
# persistence is the right lever, and dropping the recall threshold instead
# would cost real survivors.
#
# What it does NOT fix: an ID switch, where one person picks up a second ID
# after an occlusion. Both halves persist, so both are confirmed and the count
# is one too many. That needs a better tracker, not a longer threshold, and the
# dashboard states the limitation rather than implying the filter removes it.
#
# ── Why a DURATION and not a frame count ───────────────────────────
# MIN_TRACK_FRAMES is derived, never typed. The same rule has to mean the same
# thing in two places that run at very different rates:
#
#     24 fps    the demo clip           2.5 s = 60 frames
#   ~1.5 fps    Raspberry Pi 4, CPU     2.5 s =  3 frames
#
# A hardcoded 60 would be 2.5 s here and 40 s on the Pi, where it would reject
# every survivor in the flight. A hardcoded 3 would be 2.5 s on the Pi and an
# eighth of a second here, which filters nothing. Neither number is wrong; the
# unit is. "Seen for two and a half seconds" is the rule, and the frame count
# is whatever that works out to at the rate actually being processed.
#
# 2.5 s is long enough to outlast the flicker measured above and short enough
# that a person crossing the frame is still confirmed well before they leave
# it — median track length on this clip is 11 frames, and the tracks that
# clear 60 are the ones the eye also reads as people.
MIN_TRACK_SECONDS: float = 2.5

# Derived. `int()` truncates, so a rate slow enough to make this 0 or 1 leaves
# the rule as a no-op rather than an accidental filter — every track appears in
# at least one frame. `backend.tracks` floors it at 1 so the arithmetic that
# reads it cannot go negative.
MIN_TRACK_FRAMES: int = int(MIN_TRACK_SECONDS * CLIP_FPS)

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

# How far past a threshold a score has to travel before the band actually
# changes. A survivor in "high" becomes "critical" at 0.75 + this, and falls
# back to "high" at 0.75 - this; the same margin applies at every cut.
#
# The thresholds above are the rule. This is the DEADBAND around them, and it
# exists because a band is a state that gets re-read, not a one-off verdict.
# The confidence term is the confidence of each track's latest detection, and
# that figure jitters frame to frame — so a track parked near a cut does not
# sit there, it oscillates across it. On the current clip the event log shows
# single tracks changing band five times in nine seconds, which tells a reader
# the assessment is unstable when what is actually unstable is the detector's
# confidence in one box.
#
# 0.03 is small on purpose: three points of a 0-1 score, an eighth of the
# quarter-width bands it guards. Wide enough to swallow the observed jitter,
# narrow enough that a survivor whose score genuinely moves between bands still
# moves — a real escalation clears 0.78 easily, and a score that only ever
# reaches 0.76 was never a confident "critical".
#
# This is NOT the same lever as EVENT_SAMPLE_INTERVAL_S. Sampling decides how
# OFTEN the question is asked; hysteresis decides how much evidence a change of
# ANSWER needs. Sampling alone still reports a flip whenever two consecutive
# samples land on opposite sides of a cut, which is exactly what the log shows.
#
# It is a disclosed design decision, not hidden smoothing: `/api/config` sends
# it and the dashboard's priority reference panel states it beside the
# thresholds, so a judge reads the margin off the screen rather than wondering
# why a score of 0.76 is sitting in the "high" row.
BAND_HYSTERESIS: float = 0.03

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
# confirms a new track — that is the one thing which provably changes every
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

"""Persistence filtering — which track IDs are confirmed survivors.

A unique track ID is not a survivor. CONFIDENCE_THRESHOLD is set low on
purpose (CLAUDE.md: a missed survivor cannot be recovered), and the price of
that choice is that the detector reports things which are person-shaped for a
moment and the tracker gives each of them an ID. On the current clip the raw
tracker emits 333 IDs; 310 of them are gone inside two seconds.

This module holds the one rule that separates the two, so that
`/api/survivors` and `backend.events` cannot apply different versions of it:

    a track is a confirmed survivor once it has appeared in at least
    MIN_TRACK_FRAMES frames, and it becomes one at the frame where its
    MIN_TRACK_FRAMES-th detection lands.

The second half of that sentence is what makes the dashboard honest during
playback rather than only at the end. Confirmation is an event with a time: a
track first seen at frame 100 is not a survivor at frame 100, it is a survivor
at frame 160. Filtering on the whole-clip total alone would confirm it the
moment it appeared, using evidence the clip has not shown yet — the survivor
count would run ahead of the footage, which is the one thing a replay
dashboard must never do.

Nothing here filters `detections.json`, and nothing writes to it. The raw file
stays complete — it is the model's actual output and the video overlay draws
every box in it. Confirmation is a display decision made server-side, on the
way out.

What this does NOT fix, and the dashboard says so rather than implying
otherwise: an ID switch, where one person picks up a second ID after an
occlusion. Both halves persist past the threshold, so both are confirmed and
the survivor count is one too many. That is a tracker problem — see
MIN_TRACK_SECONDS in `backend.config`.
"""

from typing import Dict, List, Sequence, Set

from backend import config
from backend.schemas import Detection


def min_track_frames() -> int:
    """The persistence threshold in frames, floored at 1.

    `config.MIN_TRACK_FRAMES` is `int(MIN_TRACK_SECONDS * CLIP_FPS)`, and at a
    slow enough frame rate that truncates to 0 — on a Raspberry Pi 4 running
    at ~1.5 fps the same 2.5 s rule is only 3 frames, and a slower model would
    take it under 1. A threshold of 0 would make `frames[threshold - 1]` read
    the LAST element rather than the first, which would confirm every track at
    the frame it was last seen: a silent, plausible-looking inversion.

    Flooring at 1 makes the degenerate case a no-op instead — every track
    appears in at least one frame, so nothing is filtered and nothing is
    mis-dated. The rule stops applying at rates that slow, which is the honest
    behaviour: 2.5 seconds of evidence is not available in under one frame.
    """
    return max(1, config.MIN_TRACK_FRAMES)


def confirmation_frames(detections: Sequence[Detection]) -> Dict[int, int]:
    """Confirmed tracks and the frame each was confirmed on.

    :param detections: every record for the clip, in any order
    :returns: `track_id` -> the frame its MIN_TRACK_FRAMES-th detection landed
              on. Tracks that never reach the threshold are absent, so
              membership of the returned mapping *is* the confirmed roster and
              a caller cannot check one and read the other.

    Untracked detections (`track_id == -1`) take no part. They are real
    detections and the video overlay draws them, but two of them may be one
    person, so there is no identity to accumulate evidence against.

    Distinct FRAMES, not record count. A tracker emits one box per track per
    frame so on well-formed input the two are the same number, but the rule is
    written in frames and a duplicated record should not buy a track a
    fractional second of persistence it did not earn.
    """
    frames_by_track: Dict[int, Set[int]] = {}
    for detection in detections:
        if detection.track_id < 0:
            continue
        frames_by_track.setdefault(detection.track_id, set()).add(detection.frame_id)

    threshold = min_track_frames()
    confirmed: Dict[int, int] = {}
    for track_id, frames in frames_by_track.items():
        if len(frames) < threshold:
            continue
        # The threshold-th frame in ascending order — the instant the track had
        # accumulated enough evidence, not the instant it first appeared.
        ordered: List[int] = sorted(frames)
        confirmed[track_id] = ordered[threshold - 1]
    return confirmed

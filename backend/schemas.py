"""Pydantic models for anything crossing the API boundary.

`Detection` mirrors the perception data contract in CLAUDE.md exactly. That
format is agreed across detection, tracking, localization and the dashboard —
it must not be changed unilaterally.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class Detection(BaseModel):
    """One detected person in one frame."""

    frame_id: int = Field(..., ge=0, description="Zero-indexed frame number")
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[x1, y1, x2, y2] in source-resolution pixels",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    track_id: int = Field(..., description="Persistent per-person ID; -1 = untracked")
    class_id: int = Field(0, alias="class", description="0 = person")

    model_config = {"populate_by_name": True}


class Health(BaseModel):
    """Liveness response for the dashboard's connection indicator."""

    status: str
    service: str
    version: str


class ClipConfig(BaseModel):
    """The tunable constants the dashboard needs, as one object.

    Every value here is something a judge may ask "where does that number come
    from?" about. They live in `backend/config.py`; this model is how they
    reach the frontend so the two cannot drift apart by hand-editing.

    The frontend keeps its own copy of these as a fallback and shows an offline
    badge when it is using it — the dashboard has to render with the backend
    switched off (CLAUDE.md, demo-day constraint 2) — but whenever the backend
    is reachable, this is the single source of truth.
    """

    clip_fps: float = Field(..., gt=0, description="Frame rate of the demo clip")
    source_width: int = Field(..., gt=0, description="Width bboxes are expressed in")
    source_height: int = Field(..., gt=0, description="Height bboxes are expressed in")
    confidence_threshold: float = Field(..., ge=0.0, le=1.0)
    altitude_m: float = Field(..., gt=0, description="Fixed drone altitude for the clip")
    camera_fov_deg: float = Field(..., gt=0, lt=180, description="Horizontal FOV, nadir")
    origin_lat: float = Field(
        ..., ge=-90, le=90, description="GPS origin, frame centre at frame 0"
    )
    origin_lon: float = Field(..., ge=-180, le=180)
    drone_speed_ms: float = Field(
        ..., ge=0, description="Assumed constant ground speed along the track"
    )
    drone_heading_deg: float = Field(
        ...,
        ge=0,
        lt=360,
        description="Assumed track bearing; 0 = north, 90 = east, clockwise",
    )

    # Derived, not configured: the width of ground one frame covers, from
    # `localize.ground_sample_distance` — the same function the survivor
    # positions come out of. It is sent rather than left to the frontend so
    # the footprint on the mission-parameters panel and the footprint the map
    # pins were computed with are one number, and the panel can honestly tag
    # the row "derived" and print the formula that produced it.
    ground_footprint_m: float = Field(
        ..., gt=0, description="2 * H * tan(FOV / 2) — frame ground width, metres"
    )

    # The only value on the dashboard that could ever be tagged "measured",
    # and it is null until someone measures it. The panel renders a dash and
    # "not yet measured" while it is null rather than inventing a plausible
    # number; nothing else changes when the real figure lands here.
    device_fps: Optional[float] = Field(
        None, gt=0, description="Measured on-device inference FPS; null = not benchmarked"
    )
    device_name: str = Field(..., description="The device that figure refers to")

    # Priority scoring. The dashboard prints the formula next to the ranked
    # table using these, so what a judge reads on screen is the arithmetic that
    # actually ran rather than a caption someone has to remember to update.
    weight_confidence: float = Field(..., ge=0)
    weight_cluster_size: float = Field(..., ge=0)
    weight_hazard_proximity: float = Field(..., ge=0)
    cluster_radius_m: float = Field(
        ..., gt=0, description="Survivors within this range count as clustered"
    )
    hazard_count: int = Field(
        ...,
        ge=0,
        description=(
            "Known hazard positions. 0 means the hazard term is not scored at "
            "all — hazard classification is Phase 2 — not that the area is clear"
        ),
    )
    # How often the mission event log re-assesses priority, in seconds of
    # playback. The log panel states this on screen, so the disclosure follows
    # backend/config.py rather than a number someone typed into a caption.
    event_sample_interval_s: float = Field(
        ..., gt=0, description="Playback seconds between priority re-assessments"
    )

    # The three cuts of the four-band priority ramp. The dashboard prints them
    # verbatim, so changing backend/config.py changes what is on screen.
    priority_medium_at: float = Field(..., ge=0.0, le=1.0)
    priority_high_at: float = Field(..., ge=0.0, le=1.0)
    priority_critical_at: float = Field(..., ge=0.0, le=1.0)


class Survivor(BaseModel):
    """One de-duplicated person, at their most recent known position.

    One record per unique `track_id`. This is the count that matters — the raw
    detection total counts the same person once per frame they appear in.
    Untracked detections (`track_id == -1`) are excluded: two of them might be
    one person seen twice, so they cannot be de-duplicated and counting them
    would inflate the number.

    `latitude` and `longitude` are derived server-side by `backend.localize`
    and are deliberately NOT part of the perception JSON contract.
    """

    track_id: int = Field(..., ge=0)
    latitude: float
    longitude: float
    confidence: float = Field(..., ge=0.0, le=1.0, description="Of the latest detection")
    first_frame: int = Field(..., ge=0)
    last_frame: int = Field(..., ge=0, description="Frame the position is taken from")
    detection_count: int = Field(..., gt=0, description="Frames this track appears in")

    # Derived server-side by `backend.priority`, like latitude and longitude and
    # for the same reason: the perception JSON contract carries what the model
    # saw, not what the dashboard concluded from it.
    priority: float = Field(
        ..., ge=0.0, le=1.0, description="Weighted rescue-priority score"
    )
    priority_band: str = Field(
        ...,
        description="Ordinal priority ramp band: low | medium | high | critical",
    )
    cluster_size: int = Field(
        ...,
        ge=0,
        description="Other survivors within CLUSTER_RADIUS_M of this one",
    )


class MissionEvent(BaseModel):
    """One thing that happened during the clip, at the frame it happened on.

    The dashboard's event log renders these against the playback clock. Every
    field is derived from the detection records by `backend.events` — nothing
    here is authored, and nothing here is a status message someone wrote for a
    demo. See the demo footage policy in CLAUDE.md: a log line that cannot be
    traced back to a detection is the same failure as a hand-drawn box.

    Two kinds cross this boundary, and only two, because only these two need
    `backend.localize` and `backend.priority` to be derived at all:

      `cluster_formed`  a set of survivors first found within CLUSTER_RADIUS_M
                        of each other. `track_ids` is the whole membership.

      `priority_band`   a survivor's band was assessed. `from_band` is null on
                        the first assessment of a track and carries the
                        previous band on every change after that.

    The log's other lines — replay start, each track's first detection, the
    end-of-clip summary — are NOT here. The frontend derives those from the
    survivor roster it already holds, so the number of acquisition lines *is*
    the header's survivor count rather than a second tally that has to agree
    with it.
    """

    frame_id: int = Field(..., ge=0, description="Frame the event happened on")
    kind: str = Field(..., description="cluster_formed | priority_band")

    # priority_band only.
    track_id: Optional[int] = Field(None, ge=0)
    from_band: Optional[str] = Field(
        None, description="Previous band; null on a track's first assessment"
    )
    to_band: Optional[str] = Field(None, description="Band assessed at this frame")
    score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="The score that produced `to_band`"
    )

    # cluster_formed only. Sorted, so the rendered line is stable between runs.
    track_ids: List[int] = Field(
        default_factory=list, description="Cluster membership, ascending"
    )

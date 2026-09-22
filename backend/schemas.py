"""Pydantic models for anything crossing the API boundary.

`Detection` mirrors the perception data contract in CONVENTIONS.md exactly. That
format is agreed across detection, tracking, localization and the dashboard —
it must not be changed unilaterally.
"""

from typing import Dict, List, Optional

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
    switched off (CONVENTIONS.md, demo-day constraint 2) — but whenever the backend
    is reachable, this is the single source of truth.
    """

    clip_fps: float = Field(..., gt=0, description="Frame rate of the demo clip")
    source_width: int = Field(..., gt=0, description="Width bboxes are expressed in")
    source_height: int = Field(..., gt=0, description="Height bboxes are expressed in")
    confidence_threshold: float = Field(..., ge=0.0, le=1.0)

    # The input size the served detections were actually produced at. It is a
    # property of the file, not a setting the dashboard could change, so it
    # travels with the constants it has to be read alongside: a confidence
    # threshold means something different at 640 than at 960, and a judge
    # asking why the tracker fragments a person into three IDs is asking about
    # this number.
    detection_imgsz: int = Field(
        ..., gt=0, description="Model input size the detections were produced at"
    )

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

    # The persistence rule, sent as BOTH the duration and the frame count it
    # works out to at `clip_fps`. The duration is the rule; the frame count is
    # what it means for this clip, and the header needs it to explain the gap
    # between the tracker's ID count and the confirmed survivor count. Sending
    # both means the dashboard states the rule in the unit it is written in and
    # the unit it is applied in, without multiplying anything itself.
    min_track_seconds: float = Field(
        ..., gt=0, description="How long a track must persist to be a survivor"
    )
    min_track_frames: int = Field(
        ...,
        ge=0,
        description=(
            "That duration in frames at clip_fps. 0 or 1 means the rule is a "
            "no-op at this frame rate, not that filtering was switched off"
        ),
    )

    # The three cuts of the four-band priority ramp. The dashboard prints them
    # verbatim, so changing backend/config.py changes what is on screen.
    priority_medium_at: float = Field(..., ge=0.0, le=1.0)
    priority_high_at: float = Field(..., ge=0.0, le=1.0)
    priority_critical_at: float = Field(..., ge=0.0, le=1.0)

    # A BOOLEAN, never the URL. The dashboard needs to say "no channel
    # configured" honestly, and that needs one bit; shipping the endpoint
    # itself would put a delivery address into every browser that loads the
    # page and into any screenshot of the network tab. CONVENTIONS.md's rule about
    # private endpoints applies to what the API serves, not only to what git
    # tracks.
    alert_channel_configured: bool = Field(
        ...,
        description=(
            "Whether an alert channel is configured. False means queued "
            "alerts have nowhere to go yet — not that there is nothing to send"
        ),
    )

    # The deadband around those cuts. Sent for the same reason the cuts are:
    # the priority reference panel states it beside them, so a judge looking at
    # a survivor scored 0.76 in the "high" row reads why off the screen. It is
    # a disclosed design decision, not hidden smoothing, and shipping it in the
    # same object as the thresholds is what makes that true on the dashboard
    # rather than only in a comment.
    band_hysteresis: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "How far past a cut a score must travel before the band changes. "
            "0 means the thresholds apply exactly, with no deadband"
        ),
    )


class Survivor(BaseModel):
    """One CONFIRMED person, at their most recent known position.

    One record per unique `track_id` that has persisted for at least
    `MIN_TRACK_SECONDS` — see `backend.tracks` for the rule and why a raw track
    ID is not a survivor. Tracks below the threshold are absent entirely: this
    list is the confirmed roster, so its length is the confirmed count and no
    caller has to filter it again.

    Untracked detections (`track_id == -1`) are excluded for a different
    reason, and it is worth keeping the two apart. An untracked box has no
    identity to accumulate evidence against, so it cannot be de-duplicated at
    all; a short track has an identity, and the evidence for it was too thin.

    `latitude`, `longitude` and the priority fields are derived server-side and
    are deliberately NOT part of the perception JSON contract.
    """

    track_id: int = Field(..., ge=0)
    # The MEDIAN of every confirmed position for this track, not one detection's
    # box — a single bad box can drag a mean and barely move a median, so the
    # median is the more honest pin. Absolute projection
    # (`localize.bbox_to_latlon`, moving origin).
    latitude: float
    longitude: float
    confidence: float = Field(..., ge=0.0, le=1.0, description="Of the latest detection")
    first_frame: int = Field(..., ge=0)

    # When this track EARNED its place on the roster: the frame its
    # MIN_TRACK_FRAMES-th detection landed on, which is always >= first_frame.
    #
    # The dashboard filters on this, not on `first_frame`. A track first seen
    # at frame 100 and confirmed at frame 160 is not a survivor at frame 130 —
    # confirming it there would count evidence the clip has not played yet, and
    # the header's survivor figure would run ahead of the footage under it.
    confirmed_frame: int = Field(
        ..., ge=0, description="Frame this track reached the persistence threshold"
    )

    last_frame: int = Field(
        ..., ge=0, description="Frame of the track's latest detection"
    )
    detection_count: int = Field(
        ..., gt=0, description="Frames this track appears in; >= MIN_TRACK_FRAMES"
    )

    # How far the median pin above sits from the single estimate furthest from
    # it, in metres — the error bar on the map pin. Centimetres means the
    # projection agrees with itself; tens of metres means assumed altitude or
    # frame width is wrong. It is the dashboard's one honest check that the
    # pixel-to-GPS maths is self-consistent, and it is a diagnostic, not a
    # survey-grade accuracy claim.
    position_spread_m: float = Field(
        ...,
        ge=0.0,
        description=(
            "Max distance from the median position to any single estimate, "
            "metres. Small = the projection agrees with itself"
        ),
    )

    # Which connected component this survivor belongs to, in reference-frame
    # geometry (single linkage within CLUSTER_RADIUS_M). Group letter "A",
    # "B", ... labelled in stable order. This is a DISTINCT quantity from
    # `cluster_size` above: `group_size` is the whole component INCLUDING this
    # survivor, `cluster_size` is their DIRECT neighbours EXCLUDING self. A
    # chain of people 14 m apart is one group of several and two neighbours
    # each — both true, and the dashboard labels them so 22 and 23 do not read
    # as a contradiction.
    group_id: str = Field(
        ..., description="Connected component label, e.g. \"A\". Every survivor belongs to one"
    )
    group_size: int = Field(
        ...,
        ge=1,
        description="Members of this survivor's component, INCLUDING self",
    )

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

    # The cluster term as it entered the score, or null when it did not.
    #
    # Null means the term came out IDENTICAL for every survivor — one group
    # containing everybody, or nobody with a neighbour — so it could not rank
    # anyone and was dropped, with the remaining weights renormalised. It does
    # not mean nobody is nearby: `cluster_size` above says how many are, and
    # stays true either way. The dashboard reads this to say "cluster size did
    # not differentiate on this clip" rather than printing a term that looks
    # scored but ordered nothing. Same convention as the hazard term's absence
    # — see `backend.priority`.
    cluster_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Cluster term as scored, or null if it did not differentiate",
    )

    # Each scored term's weighted contribution to `priority`, keyed by term
    # name ("confidence", "cluster", "hazard"). Values round to four decimals
    # and sum to `priority`. A dropped term is ABSENT rather than present at
    # zero: a term the model never scored must not read as "checked, nothing
    # nearby". The dashboard renders this as the stacked score bar and uses it
    # to answer "why is this person above that one?" row by row.
    score_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-term weighted contributions; sums to priority. Dropped terms "
            "are absent, not zero"
        ),
    )


class MissionEvent(BaseModel):
    """One thing that happened during the clip, at the frame it happened on.

    The dashboard's event log renders these against the playback clock. Every
    field is derived from the detection records by `backend.events` — nothing
    here is authored, and nothing here is a status message someone wrote for a
    demo. See the demo footage policy in CONVENTIONS.md: a log line that cannot be
    traced back to a detection is the same failure as a hand-drawn box.

    Two kinds cross this boundary, and only two, because only these two need
    `backend.localize` and `backend.priority` to be derived at all:

      `cluster_formed`  a set of survivors first found within CLUSTER_RADIUS_M
                        of each other. `track_ids` is the whole membership.

      `cluster_grew`    the same group with a newly confirmed survivor in it —
                        a strict superset of a membership already reported.
                        `track_ids` is again the WHOLE membership, not the
                        joiners, so either kind answers "who is in this group".
                        Kept apart from `cluster_formed` because a single group
                        accumulating members emits one line per new member, and
                        calling all of them formations claims a group count the
                        geometry does not support.

      `priority_band`   a survivor's band was assessed. `from_band` is null on
                        the first assessment of a track and carries the
                        previous band on every change after that.

    The log's other lines — replay start, each track's first detection, the
    end-of-clip summary — are NOT here. The frontend derives those from the
    survivor roster it already holds, so the number of confirmation lines *is*
    the header's survivor count rather than a second tally that has to agree
    with it.
    """

    frame_id: int = Field(..., ge=0, description="Frame the event happened on")
    kind: str = Field(
        ..., description="cluster_formed | cluster_grew | priority_band"
    )

    # priority_band only.
    track_id: Optional[int] = Field(None, ge=0)
    from_band: Optional[str] = Field(
        None, description="Previous band; null on a track's first assessment"
    )
    to_band: Optional[str] = Field(None, description="Band assessed at this frame")
    score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="The score that produced `to_band`"
    )

    # Cluster kinds only. Sorted, so the rendered line is stable between runs.
    track_ids: List[int] = Field(
        default_factory=list, description="Cluster membership, ascending"
    )


class Route(BaseModel):
    """A ground route from the rescue staging point to one survivor.

    This is the path the RESCUE TEAM walks, not the path the drone flies —
    `simulation/planners.py` owns the second one. They are different problems
    with different costs: a drone flies over a collapsed building, a team goes
    around it. The dashboard labels them apart for the same reason.

    Two paths travel together on purpose. `path` avoids hazard risk;
    `direct_path` is the shortest line and ignores it. The gap between them is
    what the risk weighting bought, and it is the only honest way to show that
    "safe route" means something — a single polyline on a map is just a line.
    """

    track_id: int = Field(..., ge=0)
    priority: float = Field(..., ge=0.0, le=1.0)
    priority_band: str

    reachable: bool = Field(
        ..., description="False only if the cost grid walled the survivor in"
    )

    # False means no hazards are known, so the risk term was never scored and
    # `path` and `direct_path` are necessarily identical. Same convention as
    # the priority score's dropped hazard term: a term nobody scored is
    # reported absent, never as zero. It does NOT mean the ground is clear.
    hazard_aware: bool = Field(
        ...,
        description=(
            "Whether any hazard shaped this route. False = none known, not "
            "'area is safe'"
        ),
    )

    path: List[List[float]] = Field(
        default_factory=list, description="Risk-weighted route, [[lat, lon], ...]"
    )
    direct_path: List[List[float]] = Field(
        default_factory=list, description="Shortest route, hazard risk ignored"
    )

    length_m: float = Field(..., ge=0.0)
    direct_length_m: float = Field(..., ge=0.0)
    detour_m: float = Field(
        ..., description="What avoiding the hazards cost, in metres. 0 when none are known"
    )

    risk_max: float = Field(..., ge=0.0, le=1.0, description="Peak risk along `path`")
    risk_mean: float = Field(..., ge=0.0, le=1.0)
    direct_risk_max: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Peak risk the shortest route would have crossed — what justifies the detour",
    )


class Alert(BaseModel):
    """One thing that warranted interrupting somebody.

    Derived from the event timeline and the survivor roster by
    `backend.alerts` — never authored. `state` is the only field that is not
    derived: it is read from the delivery ledger on disk, because whether an
    alert reached anyone is a fact about the world and cannot be recomputed
    from the clip.
    """

    id: str = Field(..., description="Stable across restarts; the ledger key")
    kind: str = Field(
        ..., description="critical_survivor | cluster | hazard_proximity"
    )
    frame_id: int = Field(..., ge=0)
    mission_time_s: float = Field(
        ..., ge=0, description="Playback seconds, not wall clock"
    )

    track_id: Optional[int] = Field(None, description="Null for group alerts")
    priority: Optional[float] = Field(None, ge=0.0, le=1.0)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    detail: str

    # queued = nobody has tried. failed = a channel refused. The two are kept
    # apart so a broken webhook cannot hide behind "we are offline anyway".
    state: str = Field(..., description="queued | sent | failed")
    attempts: int = Field(..., ge=0)
    last_error: Optional[str] = None


class FlushResult(BaseModel):
    """What one delivery attempt achieved.

    `channel` is null when none is configured, in which case nothing was
    attempted and `note` says so. Reporting those alerts as failed would claim
    a delivery attempt that never happened.
    """

    channel: Optional[str] = None
    attempted: int = Field(..., ge=0)
    sent: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    queued: int = Field(..., ge=0)
    note: Optional[str] = None

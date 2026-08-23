"""ARES dashboard API.

The backend serves pre-computed detections against a playback clock — it does
not run inference. See CLAUDE.md, "Demo-day constraints".
"""

import json
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import config, localize, priority
from backend.schemas import ClipConfig, Detection, Health, Survivor

VERSION = "0.1.0"

app = FastAPI(
    title="ARES Dashboard API",
    description="Serves pre-computed survivor detections to the command dashboard.",
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=Health)
def health() -> Health:
    """Liveness check. The dashboard uses this for its connection indicator."""
    return Health(status="ok", service="ares-backend", version=VERSION)


@app.get("/api/config", response_model=ClipConfig)
def clip_config() -> ClipConfig:
    """The tunable constants, as one object.

    The frontend fetches this on load and renders from it. It keeps a fallback
    copy of the same values for when this endpoint is unreachable, and shows an
    offline badge when it falls back — but these are the real numbers, and
    changing `backend/config.py` changes the dashboard with no frontend edit.
    """
    return ClipConfig(
        clip_fps=config.CLIP_FPS,
        source_width=config.FRAME_WIDTH,
        source_height=config.FRAME_HEIGHT,
        confidence_threshold=config.CONFIDENCE_THRESHOLD,
        altitude_m=config.ALTITUDE_M,
        camera_fov_deg=config.CAMERA_FOV_DEG,
        origin_lat=config.ORIGIN_LAT,
        origin_lon=config.ORIGIN_LON,
        drone_speed_ms=config.DRONE_SPEED_MS,
        drone_heading_deg=config.DRONE_HEADING_DEG,
        weight_confidence=config.WEIGHT_CONFIDENCE,
        weight_cluster_size=config.WEIGHT_CLUSTER_SIZE,
        weight_hazard_proximity=config.WEIGHT_HAZARD_PROXIMITY,
        cluster_radius_m=config.CLUSTER_RADIUS_M,
        # len(), not a hand-kept number: the dashboard uses this to decide
        # whether to say the hazard term is scored or inactive, and that
        # sentence has to follow the list rather than someone's memory of it.
        hazard_count=len(config.HAZARDS),
        priority_serious_at=config.PRIORITY_SERIOUS_AT,
        priority_critical_at=config.PRIORITY_CRITICAL_AT,
    )


def _load_detections() -> List[Detection]:
    """Read and validate the clip's detection records.

    Read from disk per request rather than cached at startup: the file is a few
    hundred KB, and regenerating the fixture during development shows up
    immediately instead of needing a server restart.

    Both `/api/detections` and `/api/survivors` go through here, so the counts
    they imply are derived from one read of one file and cannot disagree.
    """
    path = config.FIXTURE_PATH
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"No detections file at {path.name}. Generate the development "
                f"fixture with: python tools/make_fixture.py > {path}"
            ),
        )

    try:
        with path.open() as f:
            records = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500, detail=f"{path.name} is not valid JSON: {exc}"
        ) from exc

    return [Detection.model_validate(r) for r in records]


@app.get("/api/detections", response_model=List[Detection])
def detections() -> List[Detection]:
    """Every detection record for the loaded clip, in frame order."""
    return _load_detections()


@app.get("/api/survivors", response_model=List[Survivor])
def survivors() -> List[Survivor]:
    """One record per unique `track_id`, ranked by rescue priority.

    This is the de-duplicated survivor list the map plots and the dashboard
    table ranks. Its length is the survivor count, and the dashboard counts
    these records rather than tallying track IDs a second time of its own — a
    header figure and a table that agree because they are the same list, not
    because two calculations happened to land on the same number.

    "Latest position" means the highest `frame_id` the track appears in.
    Ties cannot happen: a tracker emits one box per track per frame.

    **Sorted by priority, descending** — highest first, ties broken by
    `track_id` so the order is stable across requests. That is the order a
    rescue team would work the list in, so it is the order the API hands it
    over in rather than something the client has to know to impose.
    """
    latest: Dict[int, Detection] = {}
    first_frame: Dict[int, int] = {}
    counts: Dict[int, int] = {}

    for detection in _load_detections():
        track_id = detection.track_id
        # -1 means the tracker assigned no ID. Real detections, but they cannot
        # be de-duplicated, so they are not survivors — see Survivor's docstring.
        if track_id < 0:
            continue

        counts[track_id] = counts.get(track_id, 0) + 1

        previous_first = first_frame.get(track_id)
        if previous_first is None or detection.frame_id < previous_first:
            first_frame[track_id] = detection.frame_id

        previous = latest.get(track_id)
        if previous is None or detection.frame_id >= previous.frame_id:
            latest[track_id] = detection

    # Localize first, in track_id order. Scoring needs every position before it
    # can score any of them — the cluster term is "how many others are near
    # this one" — so the whole list is built before priority is computed.
    track_ids = sorted(latest)
    positions = []
    for track_id in track_ids:
        detection = latest[track_id]
        # Localized against the origin for *that detection's* frame, not a
        # fixed point: the drone is assumed to be flying a constant-velocity
        # track, so where the frame centre was matters. Using frame 0's origin
        # for everything would stack the whole clip into one camera footprint.
        latitude, longitude = localize.bbox_to_latlon(
            detection.bbox, detection.frame_id
        )
        positions.append((latitude, longitude, detection.confidence))

    scores = priority.score_all(positions)

    result = []
    for track_id, (latitude, longitude, _), score in zip(
        track_ids, positions, scores
    ):
        detection = latest[track_id]
        result.append(
            Survivor(
                track_id=track_id,
                latitude=latitude,
                longitude=longitude,
                confidence=detection.confidence,
                first_frame=first_frame[track_id],
                last_frame=detection.frame_id,
                detection_count=counts[track_id],
                priority=score.score,
                priority_band=score.band,
                cluster_size=score.cluster_size,
            )
        )

    # Highest priority first. `track_id` breaks ties so equal scores keep a
    # fixed order instead of shuffling between requests, which on a dashboard
    # polling this endpoint would look like the ranking changing on its own.
    result.sort(key=lambda s: (-s.priority, s.track_id))
    return result

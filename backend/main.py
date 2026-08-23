"""ARES dashboard API.

The backend serves pre-computed detections against a playback clock — it does
not run inference. See CLAUDE.md, "Demo-day constraints".
"""

import json
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import config, localize
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
    """One record per unique `track_id`, at its most recent known position.

    This is the de-duplicated survivor list the map plots. Its length is the
    survivor count — the same number the dashboard header derives from the
    detection records, because both come from `_load_detections()`.

    "Latest position" means the highest `frame_id` the track appears in.
    Ties cannot happen: a tracker emits one box per track per frame.
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

    # Sorted by track_id so the map's marker order, the eventual survivor
    # table's row order and this response are all the same stable order.
    result = []
    for track_id in sorted(latest):
        detection = latest[track_id]
        latitude, longitude = localize.bbox_to_latlon(detection.bbox)
        result.append(
            Survivor(
                track_id=track_id,
                latitude=latitude,
                longitude=longitude,
                confidence=detection.confidence,
                first_frame=first_frame[track_id],
                last_frame=detection.frame_id,
                detection_count=counts[track_id],
            )
        )
    return result

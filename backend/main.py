"""ARES dashboard API.

The backend serves pre-computed detections against a playback clock — it does
not run inference. See CONVENTIONS.md, "Demo-day constraints".
"""

import json
import statistics
from typing import Dict, List, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend import (
    alerts as alerts_module,
    config,
    events as events_module,
    localize,
    priority,
    routing,
    tracks,
)
from backend.schemas import (
    Alert,
    ClipConfig,
    Detection,
    FlushResult,
    Health,
    MissionEvent,
    Route,
    Survivor,
)

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
        detection_imgsz=config.DETECTION_IMGSZ,
        altitude_m=config.ALTITUDE_M,
        camera_fov_deg=config.CAMERA_FOV_DEG,
        origin_lat=config.ORIGIN_LAT,
        origin_lon=config.ORIGIN_LON,
        drone_speed_ms=config.DRONE_SPEED_MS,
        drone_heading_deg=config.DRONE_HEADING_DEG,
        # Computed here rather than restated: `ground_sample_distance` is what
        # `localize` scales every pixel offset by, so the footprint the panel
        # shows is arithmetically the same one the map pins came out of.
        ground_footprint_m=localize.ground_sample_distance() * config.FRAME_WIDTH,
        device_fps=config.DEVICE_FPS,
        device_name=config.DEVICE_NAME,
        weight_confidence=config.WEIGHT_CONFIDENCE,
        weight_cluster_size=config.WEIGHT_CLUSTER_SIZE,
        weight_hazard_proximity=config.WEIGHT_HAZARD_PROXIMITY,
        cluster_radius_m=config.CLUSTER_RADIUS_M,
        # len(), not a hand-kept number: the dashboard uses this to decide
        # whether to say the hazard term is scored or inactive, and that
        # sentence has to follow the list rather than someone's memory of it.
        hazard_count=len(config.HAZARDS),
        band_hysteresis=config.BAND_HYSTERESIS,
        event_sample_interval_s=config.EVENT_SAMPLE_INTERVAL_S,
        min_track_seconds=config.MIN_TRACK_SECONDS,
        # `tracks.min_track_frames()`, not `config.MIN_TRACK_FRAMES` — the
        # floor is part of the rule, so the dashboard is told the threshold
        # that will actually be applied rather than the raw multiplication.
        min_track_frames=tracks.min_track_frames(),
        priority_medium_at=config.PRIORITY_MEDIUM_AT,
        priority_high_at=config.PRIORITY_HIGH_AT,
        priority_critical_at=config.PRIORITY_CRITICAL_AT,
        # bool(), so the URL itself never leaves the backend.
        alert_channel_configured=bool(config.ALERT_WEBHOOK_URL),
    )


@app.get("/tiles/{z}/{x}/{y}.png", response_class=FileResponse)
def tile(z: int, x: int, y: int) -> FileResponse:
    """One cached OpenStreetMap tile.

    Demo-day constraint 3 in CONVENTIONS.md: map tiles need internet and venue wifi
    fails. `tools/fetch_tiles.py` downloads the tiles covering the demo area
    into `config.TILES_DIR` ahead of time, and Leaflet points here instead of
    at openstreetmap.org — so the base map survives a dead network.

    Only tiles inside the bundled box exist. A zoom or pan outside it 404s,
    which is what the map panel's existing "tiles unreachable" banner already
    handles: the pins stay, the base map goes. That is the intended fallback,
    not a failure to fix here.

    Path traversal is not a concern: `z`, `x` and `y` are typed as `int`, so
    FastAPI rejects anything that is not a bare integer before this runs and
    no separator can reach the filesystem.
    """
    path = config.TILES_DIR / str(z) / str(x) / f"{y}.png"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Tile {z}/{x}/{y} is not in the bundled set. Fetch the demo "
                f"area with: python tools/fetch_tiles.py"
            ),
        )
    # Tiles never change once fetched — they are a frozen snapshot of the demo
    # area, not a live layer — so let the browser keep them for the session
    # rather than re-asking on every pan.
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )


def _load_detections() -> List[Detection]:
    """Read and validate the clip's detection records.

    Read from disk per request rather than cached at startup: the file is a few
    hundred KB, and re-running the model over the clip shows up immediately
    instead of needing a server restart.

    Both `/api/detections` and `/api/survivors` go through here, so the counts
    they imply are derived from one read of one file and cannot disagree.
    """
    path = config.DETECTIONS_PATH
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"No detections file at {path.name}. Produce it by running the "
                f"model over the demo clip: python tools/build_demo_clip.py"
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


@app.get("/api/events", response_model=List[MissionEvent])
def events() -> List[MissionEvent]:
    """The clip's mission event timeline, in frame order.

    What the dashboard's event log plays back against the playback clock. Every
    event is derived from the same detections file the other two endpoints read
    — see `backend.events` for how, and CONVENTIONS.md's demo footage policy for why
    there is no other way to get a line into this list.

    Only the two kinds that need server-side maths are here: cluster formation,
    which needs `backend.localize`, and priority bands, which need
    `backend.priority`. Replay start, first detections and the closing summary
    are derived by the frontend from the survivor roster it already holds, so
    the log's confirmation lines are the header's survivor count rather than a
    second count of the same people.

    The final `priority_band` events assess the roster at the clip's last
    frame, which is the same computation `/api/survivors` runs — so the bands
    the log closes on are the bands the table shows, by construction.
    """
    return events_module.derive_events(_load_detections())


@app.get("/api/survivors", response_model=List[Survivor])
def survivors() -> List[Survivor]:
    """One record per CONFIRMED survivor, ranked by rescue priority.

    This is the list the map plots and the dashboard table ranks. Its length is
    the confirmed survivor count, and the dashboard counts these records rather
    than tallying track IDs a second time of its own — a header figure and a
    table that agree because they are the same list, not because two
    calculations happened to land on the same number.

    ── Persistence filtering ────────────────────────────────────────
    A track has to have appeared in at least `MIN_TRACK_FRAMES` frames to
    appear here. Tracks below that threshold are dropped, and the raw
    detections file is untouched — `/api/detections` still serves every record
    and the video overlay still draws every box. Confirmation is a display
    decision made on the way out, not an edit to the model's output.

    The gap the filter opens is real and the dashboard shows it rather than
    hiding it: the tracker emits 333 IDs on the current clip and 23 of them
    clear 2.5 seconds. That difference is the price of a 0.18 confidence
    threshold, and both numbers are on the header for exactly that reason.
    See `backend.tracks`.

    Everything downstream is computed on the CONFIRMED roster only, which is
    why the filter runs before localization rather than after: `cluster_size`
    counts how many survivors are nearby, and a flicker that lasted two frames
    is not a survivor standing next to anyone.

    "Latest position" means the highest `frame_id` the track appears in.
    Ties cannot happen: a tracker emits one box per track per frame.

    **Sorted by priority, descending** — highest first, ties broken by
    `track_id` so the order is stable across requests. That is the order a
    rescue team would work the list in, so it is the order the API hands it
    over in rather than something the client has to know to impose.

    ── Bands come from the event walk ───────────────────────────────
    `priority_band` is hysteretic: a change needs the score to clear the cut by
    BAND_HYSTERESIS, so the band depends on the track's history and not on this
    frame alone. This endpoint therefore takes each track's current band from
    `events.final_bands` — the state the mission log's own walk ends on — and
    re-scores against it rather than re-deriving one from the thresholds. The
    band in this table and the band the log closes on are then the same value
    by construction, which is the point: a survivor cannot be "critical" in the
    table and "high" in the log at the same moment.
    """
    records = _load_detections()

    # The confirmed roster and the frame each track earned its place on. Keys
    # are the whole membership test, so nothing below needs a second threshold
    # comparison that could be written differently.
    confirmed_at = tracks.confirmation_frames(records)

    latest: Dict[int, Detection] = {}
    first_frame: Dict[int, int] = {}
    counts: Dict[int, int] = {}
    # Every confirmed position per track, in any order. The median of these,
    # not a single detection, becomes the map pin — see below. One bad box can
    # drag a mean and barely move a median, and `position_spread_m` is
    # measured against this same set, so both the pin and its error bar follow
    # from one list rather than two readings that could drift apart.
    positions_by_track: Dict[int, List[Tuple[float, float]]] = {}
    reference_by_track: Dict[int, List[Tuple[float, float]]] = {}

    for detection in records:
        track_id = detection.track_id
        # -1 means the tracker assigned no ID. Real detections, but they cannot
        # be de-duplicated, so they are not survivors — see Survivor's docstring.
        if track_id < 0:
            continue

        # Too short to be a person. Dropped here rather than after scoring so
        # the cluster term never counts a flicker as somebody's neighbour.
        if track_id not in confirmed_at:
            continue

        counts[track_id] = counts.get(track_id, 0) + 1

        # Absolute position (moving origin — where the survivor IS), the same
        # projection the scoring positions and the reference-frame geometry
        # come from. Collected for EVERY confirmed detection so the median pin
        # is not one lucky box.
        positions_by_track.setdefault(track_id, []).append(
            localize.bbox_to_latlon(detection.bbox, detection.frame_id)
        )

        # The same detection with the assumed flight track held still. The
        # SPREAD is measured in here, not in the absolute positions above —
        # see the block that computes it for why.
        reference_by_track.setdefault(track_id, []).append(
            localize.bbox_to_reference_latlon(detection.bbox)
        )

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
    cluster_geometry = []
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

        # And the same detection with the flight track held still, which is the
        # geometry the cluster term counts neighbours in. The assumed track is
        # the right model for where somebody IS and the wrong one for how far
        # apart two people are, because it turns the gap between two last
        # sightings into ground distance — see
        # `localize.bbox_to_reference_latlon`. Only the map pin and the hazard
        # distance use the moving origin.
        cluster_geometry.append(localize.bbox_to_reference_latlon(detection.bbox))

    # The map pin and its error bar, from the MEDIAN of every confirmed
    # position rather than the latest detection's box. The scoring above keeps
    # using latest positions — that is what `events.final_bands` walked, so
    # changing it here would let the table's priority drift from the log's. But
    # position is a different question from score, and one bad box can drag a
    # mean and barely move a median; a single box is also a point mover while
    # the person stands still. The median of all of them is the more honest pin.
    #
    # `position_spread_m` is the furthest any single estimate sat from the
    # median of that track's estimates — how much the projection disagrees
    # with itself about one stationary person.
    #
    # IT IS MEASURED IN THE FIXED REFERENCE FRAME, NOT AGAINST THE PIN.
    #
    # Measured on the demo clip, frame-to-frame displacement of the same
    # tracks under the two projections:
    #
    #     assumed drone travel      20.8 cm/frame   (5 m/s / 24 fps)
    #     moving origin             19.9 cm/frame
    #     fixed reference frame      1.8 cm/frame   = 1.0 px at GSD 1.80 cm/px
    #
    # The moving origin advances along an ASSUMED track, so over a track's
    # lifetime the spread it produces is that assumption integrated over time —
    # 5.60 to 20.22 m, correlating +0.930 with how long the track lived. It
    # cannot distinguish a wrong altitude from a long track, which is the one
    # job it exists to do.
    #
    # This is Rule 1, applied where the guide's §6② said not to: the distance
    # between two estimates OF ONE PERSON is a relative measurement, and
    # relative measurements use the fixed frame. In it the spread reads
    # 0.45-4.12 m and a scale error would show.
    #
    # The PIN stays absolute. Where somebody is and how well we know it are
    # different questions and take different projections.
    median_position: Dict[int, Tuple[float, float]] = {}
    position_spread: Dict[int, float] = {}
    for track_id in track_ids:
        points = positions_by_track[track_id]
        lat = statistics.median(p[0] for p in points)
        lon = statistics.median(p[1] for p in points)
        median_position[track_id] = (lat, lon)

        fixed = reference_by_track[track_id]
        ref_lat = statistics.median(p[0] for p in fixed)
        ref_lon = statistics.median(p[1] for p in fixed)
        position_spread[track_id] = max(
            priority.metres_between(ref_lat, ref_lon, pt[0], pt[1]) for pt in fixed
        )

    # ── Groups: connected components of the roster ───────────────────
    # Who stands together is a RELATIVE question, so it is answered in the
    # reference-frame geometry — the same geometry `cluster_size` and the
    # cluster events come from (Rule 1). Not the moving-origin absolute
    # positions, which would manufacture metres of separation out of the time
    # gap between two last sightings.
    #
    # `group_size` is the whole connected component INCLUDING this survivor,
    # while `cluster_size` above is this survivor's DIRECT neighbours
    # EXCLUDING self. On a fully-linked patch of 23 people those are 23 and 22;
    # on a chain of people 14 m apart they are one group of several with two
    # neighbours each. Both are true; only the labels are new, and the
    # dashboard says what each counts.
    group_of: Dict[int, str] = {}
    group_size: Dict[int, int] = {}
    for component_index, members in enumerate(
        events_module.components(track_ids, cluster_geometry)
    ):
        # members is sorted ascending and components are ordered by their
        # smallest member, so the labeling is stable across requests.
        label = (
            chr(ord("A") + component_index)
            if component_index < 26
            else f"G{component_index}"
        )
        for track_id in members:
            group_of[track_id] = label
            group_size[track_id] = len(members)

    # Band history, from the same walk the event log is built from.
    #
    # Hysteresis (BAND_HYSTERESIS) means a band depends on where the track came
    # from, not only where its score is now — so scoring this frame in
    # isolation would put a survivor sitting just past a cut in the band above
    # while the event log, which watched them creep up to it, still holds them
    # below. The header, the table and the log would disagree about one person
    # on screen at once. `events.final_bands` is where the log's assessment
    # ends up, and re-scoring against it is idempotent (see `priority.band_for`),
    # so the two cannot diverge.
    previous_bands = events_module.final_bands(records, confirmed_at)
    scores = priority.score_all(
        positions,
        [previous_bands.get(track_id) for track_id in track_ids],
        cluster_geometry,
    )

    result = []
    for track_id, (latitude, longitude, _), score in zip(
        track_ids, positions, scores
    ):
        detection = latest[track_id]
        pin_lat, pin_lon = median_position[track_id]
        result.append(
            Survivor(
                track_id=track_id,
                latitude=pin_lat,
                longitude=pin_lon,
                confidence=detection.confidence,
                first_frame=first_frame[track_id],
                confirmed_frame=confirmed_at[track_id],
                last_frame=detection.frame_id,
                detection_count=counts[track_id],
                priority=score.score,
                priority_band=score.band,
                cluster_size=score.cluster_size,
                cluster_score=score.cluster_score,
                score_breakdown=score.score_breakdown,
                position_spread_m=position_spread[track_id],
                group_id=group_of[track_id],
                group_size=group_size[track_id],
            )
        )

    # Highest priority first. `track_id` breaks ties so equal scores keep a
    # fixed order instead of shuffling between requests, which on a dashboard
    # polling this endpoint would look like the ranking changing on its own.
    result.sort(key=lambda s: (-s.priority, s.track_id))
    return result


@app.get("/api/routes", response_model=List[Route])
def routes() -> List[Route]:
    """A ground route to every confirmed survivor, highest priority first.

    Built on `survivors()` rather than on the detections, so the route list and
    the rescue queue are the same sequence in the same order — one list, not
    two tallies that have to agree.

    ── What this is and is not ──────────────────────────────────────
    The cost surface is a hazard grid, not a road network. A route here says
    "approach from this side rather than that one"; it is not turn-by-turn
    navigation, and the dashboard labels it that way.

    While `config.HAZARDS` is empty — hazard classification is Phase 2 — there
    is no risk surface, every `hazard_aware` comes back False and the two paths
    in each record are identical. That is the honest state, not a failure: the
    endpoint reports that the risk term was never scored rather than returning
    a "safe" route that avoided nothing.
    """
    return [Route(**r) for r in routing.plan_routes(survivors())]


@app.get("/api/alerts", response_model=List[Alert])
def alerts() -> List[Alert]:
    """Every alert the clip justifies, with its delivery state.

    Built on `events()` and `survivors()` — the same two lists the mission log
    and the priority table render — so an alert can always be traced to the
    detections that produced it. Nothing here is authored.

    `state` comes from the append-only ledger in `backend/data/`. With no
    channel configured every alert reads `queued`, which is the honest state
    and the one the prototype ships in: the alerts exist, they are ordered, and
    nothing has carried them anywhere yet.
    """
    derived = alerts_module.derive_alerts(events(), survivors())
    return [Alert(**a) for a in alerts_module.join_state(derived)]


@app.post("/api/alerts/flush", response_model=FlushResult)
def flush_alerts() -> FlushResult:
    """Drain the queue to the configured channel, highest priority first.

    The ordering is the point. A link that returns for ten seconds should spend
    them on the survivor most likely to die, not on whichever alert happened to
    fire first — the same priority that ranks the rescue queue, applied to
    bandwidth instead of to people's time.

    Explicit rather than automatic: nothing on this dashboard should reach out
    to a network on its own during a demo. With `ALERT_WEBHOOK_URL` unset this
    attempts nothing and says why.
    """
    derived = alerts_module.derive_alerts(events(), survivors())
    return FlushResult(**alerts_module.flush(derived))

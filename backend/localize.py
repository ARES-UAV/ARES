"""Pixel -> GPS conversion for the demo clip.

Implements the flat-earth nadir projection described in CLAUDE.md. The camera
points straight down, the terrain under the clip is treated as flat, and
altitude, field of view, the frame-0 GPS origin and the flight track are fixed
constants per clip — the prototype has no live telemetry, so there is nothing
to read them from. Those constants live in `backend.config` and are not
duplicated here.

The drone moves. `ORIGIN_LAT`/`ORIGIN_LON` is where it sits at frame 0, and
`origin_for_frame` advances it along an assumed constant-velocity track from
there. That track is an assumption of exactly the same kind as the altitude —
disclosed, not measured — and it is the reason survivors spread along a flight
path instead of piling into the single 23 m footprint a hovering drone sees.

The accuracy this buys is "good enough to put a pin on the right building",
not survey grade, and the pitch says so. Above roughly 40 m a 1.7 m person
spans fewer than 24 px at 640 px input, which is where detection — not this
maths — becomes the limit.
"""

import math
from typing import Optional, Sequence, Tuple

from backend import config

# Metres per degree of latitude. Constant enough at any latitude for a clip
# that covers a few dozen metres; the longitude equivalent shrinks with
# cos(latitude) and is computed per call.
METRES_PER_DEGREE_LAT: float = 111_320.0


def ground_sample_distance(
    altitude_m: Optional[float] = None,
    fov_deg: Optional[float] = None,
    image_width: Optional[int] = None,
) -> float:
    """Metres of ground covered by one pixel.

    GSD = 2 * H * tan(FOV / 2) / image_width

    `fov_deg` is the *horizontal* field of view, so it pairs with the image
    width. Pixels are assumed square, which makes this the scale for both axes.

    Arguments default to the configured clip constants; they are parameters at
    all so the figure can be recomputed for a different altitude without
    mutating module state.
    """
    altitude = config.ALTITUDE_M if altitude_m is None else altitude_m
    fov = config.CAMERA_FOV_DEG if fov_deg is None else fov_deg
    width = config.FRAME_WIDTH if image_width is None else image_width

    return 2.0 * altitude * math.tan(math.radians(fov) / 2.0) / width


def origin_for_frame(
    frame_id: int,
    *,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    fps: Optional[float] = None,
    speed_ms: Optional[float] = None,
    heading_deg: Optional[float] = None,
) -> Tuple[float, float]:
    """Where the drone is assumed to be when frame `frame_id` was captured.

    The frame-0 origin displaced along a straight constant-velocity track:

        t        = frame_id / fps                 seconds since frame 0
        distance = speed_ms * t                   metres along the heading

    `heading_deg` is a compass bearing — 0 is north, 90 is east, increasing
    clockwise — which is the convention flight software uses and is NOT the
    mathematical convention. So north takes the cosine and east the sine, the
    opposite way round from the usual polar-to-cartesian pair. Getting that
    backwards mirrors the track across the north-east diagonal, which looks
    like a plausible flight either way.

    A constant-velocity straight line is a deliberate simplification. Nothing
    here reads telemetry; there is none. Real turns, climbs and station-keeping
    would come from a flight log, and when one exists this function is the only
    thing that has to change.
    """
    lat0 = config.ORIGIN_LAT if origin_lat is None else origin_lat
    lon0 = config.ORIGIN_LON if origin_lon is None else origin_lon
    rate = config.CLIP_FPS if fps is None else fps
    speed = config.DRONE_SPEED_MS if speed_ms is None else speed_ms
    heading = config.DRONE_HEADING_DEG if heading_deg is None else heading_deg

    distance_m = speed * (frame_id / rate)
    bearing = math.radians(heading)

    north_m = distance_m * math.cos(bearing)
    east_m = distance_m * math.sin(bearing)

    dlat = north_m / METRES_PER_DEGREE_LAT
    dlon = east_m / (METRES_PER_DEGREE_LAT * math.cos(math.radians(lat0)))

    return lat0 + dlat, lon0 + dlon


def pixel_to_latlon(
    x: float,
    y: float,
    *,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    image_width: Optional[int] = None,
    image_height: Optional[int] = None,
    gsd: Optional[float] = None,
) -> Tuple[float, float]:
    """Convert a pixel in the source frame to (latitude, longitude).

    The origin is the *centre* of the frame: the drone is assumed to sit
    directly above `(origin_lat, origin_lon)` looking down, so the centre pixel
    is that coordinate and everything else is an offset from it.

    That origin is the drone's position **for the frame this pixel came from**,
    not a fixed point — the drone flies. Callers working from a detection
    record should go through `bbox_to_latlon`, which resolves the frame's
    origin from `origin_for_frame`. The bare defaults here are the frame-0
    position, which is only correct for frame 0.

    Note the sign on the northing. Image y grows downward while latitude grows
    northward, so a pixel below the centre of the frame is *south* of the
    origin and its dlat must be negative. The formula in CLAUDE.md is written
    in terms of a ground offset and leaves that flip implicit; getting it wrong
    mirrors every survivor across the drone's position, which looks plausible
    on a map and is completely wrong.
    """
    lat0 = config.ORIGIN_LAT if origin_lat is None else origin_lat
    lon0 = config.ORIGIN_LON if origin_lon is None else origin_lon
    width = config.FRAME_WIDTH if image_width is None else image_width
    height = config.FRAME_HEIGHT if image_height is None else image_height
    scale = ground_sample_distance() if gsd is None else gsd

    east_m = (x - width / 2.0) * scale
    north_m = (height / 2.0 - y) * scale  # y grows down, north grows up

    dlat = north_m / METRES_PER_DEGREE_LAT
    dlon = east_m / (METRES_PER_DEGREE_LAT * math.cos(math.radians(lat0)))

    return lat0 + dlat, lon0 + dlon


def bbox_to_latlon(
    bbox: Sequence[float],
    frame_id: int,
    **kwargs: float,
) -> Tuple[float, float]:
    """Ground position of one detection, from its `[x1, y1, x2, y2]` box.

    The box centre is used. Under a nadir camera a person's footprint sits
    directly beneath them, so the centre of the box is the best single-point
    estimate available — unlike an oblique view, where the bottom edge would be
    the ground contact point.

    `frame_id` is required rather than optional because the answer genuinely
    depends on it: the same pixel in frame 0 and in frame 299 is 62 m apart on
    the ground at the configured speed. A default would silently pick one.

    An explicit `origin_lat`/`origin_lon` in `kwargs` still wins, so a caller
    with a real telemetry fix can supply it and bypass the assumed track.
    """
    if kwargs.get("origin_lat") is None or kwargs.get("origin_lon") is None:
        origin_lat, origin_lon = origin_for_frame(frame_id)
        kwargs.setdefault("origin_lat", origin_lat)
        kwargs.setdefault("origin_lon", origin_lon)

    x1, y1, x2, y2 = bbox
    return pixel_to_latlon((x1 + x2) / 2.0, (y1 + y2) / 2.0, **kwargs)


# The frame every *relative* measurement is taken in.
#
# Frame 0, which is where the drone is assumed to be at the start of the clip,
# but the specific value is not what matters — any single frame would do. What
# matters is that ONE frame is used for every survivor, so that the assumed
# flight track cancels out of the distance between two of them.
CLUSTER_REFERENCE_FRAME: int = 0


def bbox_to_reference_latlon(bbox: Sequence[float]) -> Tuple[float, float]:
    """Ground position of one detection with the assumed flight track held still.

    Same projection as `bbox_to_latlon`, with every detection localized against
    a single frame's origin instead of its own. The result is NOT where the
    person is — for that, use `bbox_to_latlon`, which is what the map plots and
    what a hazard distance is measured against. It is where they sat in the
    camera's own geometry, which is the only spatial relationship this clip
    actually observed.

    ── Why a relative measurement needs its own projection ──────────
    `origin_for_frame` advances the origin along an ASSUMED constant-velocity
    track. That is the right call for an absolute position: a survivor last
    seen forty frames ago was last seen somewhere the drone has since flown
    past, and pinning them under the aircraft's current position would be
    worse. But it makes the distance between two survivors depend on how far
    apart in TIME their last sightings were, and at 5 m/s a three-second gap
    manufactures fifteen metres of separation between two people who may have
    been standing next to each other.

    Nothing measured that separation. It is an artifact of an assumption, and
    it has no business deciding a rescue ranking — on the current clip it put
    the highest-confidence detection in the whole scene second from the bottom
    of the queue, because its last sighting was three seconds after everyone
    else's. Measuring the cluster term here instead confines the flight-track
    assumption to the map pin, where it is disclosed, and keeps it out of the
    scoring.

    The choice of reference frame does not affect any distance: shifting every
    point by the same offset leaves the gaps between them unchanged.
    """
    return bbox_to_latlon(bbox, CLUSTER_REFERENCE_FRAME)

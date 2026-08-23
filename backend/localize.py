"""Pixel -> GPS conversion for the demo clip.

Implements the flat-earth nadir projection described in CLAUDE.md. The camera
points straight down, the terrain under the clip is treated as flat, and
altitude, field of view and the GPS origin are fixed constants per clip — the
prototype has no live telemetry, so there is nothing to read them from. Those
constants live in `backend.config` and are not duplicated here.

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
    directly above `(ORIGIN_LAT, ORIGIN_LON)` looking down, so the centre pixel
    is that coordinate and everything else is an offset from it.

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
    **kwargs: float,
) -> Tuple[float, float]:
    """Ground position of one detection, from its `[x1, y1, x2, y2]` box.

    The box centre is used. Under a nadir camera a person's footprint sits
    directly beneath them, so the centre of the box is the best single-point
    estimate available — unlike an oblique view, where the bottom edge would be
    the ground contact point.
    """
    x1, y1, x2, y2 = bbox
    return pixel_to_latlon((x1 + x2) / 2.0, (y1 + y2) / 2.0, **kwargs)

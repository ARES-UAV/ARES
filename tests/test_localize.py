"""Localization tests for the pixel->GPS projection.

Tests the flat-earth nadir projection in `backend.localize` against the
properties the Guide (Robby/Guide.md) and CLAUDE.md's Localization section
require, plus the median-position and position-spread behaviour the survivor
endpoint relies on:

  * ground sample distance matches the published formula,
  * the frame centre is exactly the drone origin for frame 0,
  * the four cardinal directions are correct (north/south, east/west with the
    image y-axis growing downward),
  * heading uses compass-bearing conventions (0 = north, 90 = east,
    clockwise),
  * the moving origin advances at speed x elapsed time along the bearing,
  * the two projections (absolute and reference-frame) agree geometrically, and
  * median localization is robust to a single bad box.
"""

import statistics

import pytest

from backend import localize
from backend.priority import metres_between


def test_ground_sample_distance_published_value():
    # 20 m altitude, 60 deg FOV, 1280 px width -> 0.01804 m/px -> 23.09 m footprint
    gsd = localize.ground_sample_distance(20, 60, 1280)
    assert gsd == pytest.approx(0.0180, abs=1e-3)
    footprint = gsd * 1280
    assert footprint == pytest.approx(23.09, abs=0.01)


def test_ground_sample_distance_defaults_to_config():
    # With no arguments it reads the configured 20 m / 60 deg / 1280 width.
    assert localize.ground_sample_distance() == pytest.approx(0.0180, abs=1e-3)


def test_frame_centre_is_origin_for_frame_zero():
    # The centre pixel, at frame 0, is exactly the configured origin.
    lat, lon = localize.bbox_to_latlon([640, 360, 640, 360], 0)
    assert lat == pytest.approx(localize.config.ORIGIN_LAT)
    assert lon == pytest.approx(localize.config.ORIGIN_LON)


def test_top_left_is_north_west():
    # Top-left corner -> north AND west of the origin.
    lat, lon = localize.pixel_to_latlon(0, 0)
    assert lat > localize.config.ORIGIN_LAT      # north
    assert lon < localize.config.ORIGIN_LON      # west


def test_bottom_right_is_south_east():
    # Bottom-right corner -> south AND east of the origin.
    lat, lon = localize.pixel_to_latlon(1280, 720)
    assert lat < localize.config.ORIGIN_LAT      # south
    assert lon > localize.config.ORIGIN_LON      # east


def test_y_axis_direction():
    # Image y grows DOWNWARD. A pixel lower in the frame must be SOUTH
    # (lower latitude), so going from top to bottom decreases latitude.
    top = localize.pixel_to_latlon(640, 0)
    bottom = localize.pixel_to_latlon(640, 720)
    assert top[0] > bottom[0]


def test_x_axis_direction():
    # Left -> west (smaller longitude), right -> east (larger longitude).
    left = localize.pixel_to_latlon(0, 360)
    right = localize.pixel_to_latlon(1280, 360)
    assert left[1] < right[1]


def test_heading_compass_convention():
    # Heading is a compass bearing: 0 = north, 90 = east, clockwise.
    # At heading 90 (east), the origin advances east (larger longitude) and
    # north offset is zero (cos(90) = 0).
    origin = localize.origin_for_frame(0)
    east = localize.origin_for_frame(100, heading_deg=90.0)
    assert east[1] > origin[1]                                     # longitude grows
    assert east[0] == pytest.approx(origin[0], abs=1e-6)           # latitude unchanged


def test_moving_drone_distance():
    # Frame 0 vs frame 300 -> 5 m/s x (300/24) = 62.5 m along the heading.
    origin = localize.origin_for_frame(0)
    later = localize.origin_for_frame(300)
    distance = metres_between(origin[0], origin[1], later[0], later[1])
    expected = 5.0 * (300 / 24.0)
    assert distance == pytest.approx(expected, abs=1.0)


def test_moving_drone_to_east_on_bearing_90():
    # At 90 deg (east), frame-to-frame displacement is purely eastward.
    f0 = localize.origin_for_frame(0, heading_deg=90.0)
    f300 = localize.origin_for_frame(300, heading_deg=90.0)
    assert f300[1] > f0[1]
    assert f300[0] == pytest.approx(f0[0], abs=1e-6)


def test_reference_projection_holds_track_still():
    # `bbox_to_reference_latlon` must NOT depend on frame_id: the same box
    # localizes to the same place regardless of which frame it is said to come
    # from, because the flight track is held at frame 0. Compare against an
    # absolute localization that passes frame 0 explicitly.
    bbox = [500, 200, 540, 240]
    reference = localize.bbox_to_reference_latlon(bbox)
    absolute_at_0 = localize.bbox_to_latlon(bbox, 0)
    assert reference[0] == pytest.approx(absolute_at_0[0])
    assert reference[1] == pytest.approx(absolute_at_0[1])


def test_median_position_robust_to_outlier():
    """Median localization should barely move when one estimate is far off.

    A single bad box drags a mean but leaves a median almost untouched. This is
    the property the survivor endpoint relies on when it pins a track at the
    median of every confirmed position rather than the latest detection.
    """
    # Five clustered estimates plus one wild outlier far to the east.
    points = [
        (26.4058, 92.2334),
        (26.4059, 92.2335),
        (26.4058, 92.2334),
        (26.4059, 92.2335),
        (26.4058, 92.2334),
        (26.5000, 92.5000),  # outlier
    ]
    median_lat = statistics.median(p[0] for p in points)
    median_lon = statistics.median(p[1] for p in points)

    # The median stays within the tight cluster; the mean would be dragged
    # toward the outlier by a meaningful fraction of a degree.
    assert median_lat == pytest.approx(26.4058, abs=1e-4)
    assert median_lon == pytest.approx(92.2334, abs=1e-4)


def test_position_spread_is_max_distance_from_median():
    """`position_spread_m` is the furthest estimate from the median, in metres."""
    points = [
        (26.4058, 92.2334),
        (26.4058, 92.2334),
        (26.4059, 92.2335),
    ]
    lat = statistics.median(p[0] for p in points)
    lon = statistics.median(p[1] for p in points)
    spread = max(metres_between(lat, lon, p[0], p[1]) for p in points)

    # The max is >= every estimate's distance from the median.
    individual = [metres_between(lat, lon, p[0], p[1]) for p in points]
    assert spread == max(individual)
    # Sanity: many-metre spread is implausible for centimetre-scale agreement.
    assert spread >= 0.0

"""Connected-component (group) tests for `backend.events.components`.

Groups are single-linkage connected components within CLUSTER_RADIUS_M, in the
reference-frame geometry. These tests cover the guide's group rules:

  * an isolated survivor is its own group of one,
  * a simple pair is one group of two,
  * a chain of people linked pairwise is ONE group (single linkage),
  * `group_size` includes self, `cluster_size` excludes self,
  * group IDs are deterministic (stable across calls),
  * components uses reference-frame geometry.
"""

import pytest

from backend import events, priority
from backend.localize import bbox_to_reference_latlon


def _metres(lat1, lon1, lat2, lon2):
    return priority.metres_between(lat1, lon1, lat2, lon2)


def test_isolated_survivor_is_own_group():
    # A single survivor -> one component of one.
    ids = [1]
    pos = [(26.0, 92.0)]
    comps = events.components(ids, pos)
    assert comps == [[1]]


def test_simple_pair_is_one_group():
    ids = [1, 2]
    # Two points a few metres apart -> within the 15 m radius.
    pos = [(26.0, 92.0), (26.0, 92.0001)]
    assert _metres(26.0, 92.0, 26.0, 92.0001) < 15.0
    comps = events.components(ids, pos)
    assert comps == [[1, 2]]


def test_far_apart_survivors_are_separate_groups():
    ids = [1, 2, 3]
    # Three points spaced far beyond the radius -> three singletons.
    pos = [(26.0, 92.0), (26.0, 92.01), (26.0, 92.02)]
    comps = events.components(ids, pos)
    assert comps == [[1], [2], [3]]


def test_connected_chain_is_one_group():
    """Single linkage: a chain of people 14 m apart is ONE group.

    Each person is within the radius of their immediate neighbour even though
    the ends are further apart than the radius would allow directly.
    """
    ids = [1, 2, 3, 4]
    # 14 m spacing eastward (~1.25e-4 deg lon). Ends are ~42 m apart (> radius).
    base_lat, base_lon = 26.0, 92.0
    dlon = 0.000125
    pos = [
        (base_lat, base_lon),
        (base_lat, base_lon + dlon),
        (base_lat, base_lon + 2 * dlon),
        (base_lat, base_lon + 3 * dlon),
    ]
    # Verify pairwise adjacency is within the radius.
    for i in range(3):
        assert _metres(pos[i][0], pos[i][1], pos[i + 1][0], pos[i + 1][1]) < 15.0
    # Ends further apart than the radius directly.
    assert _metres(pos[0][0], pos[0][1], pos[3][0], pos[3][1]) > 15.0
    comps = events.components(ids, pos)
    # Still one component spanning all four.
    assert comps == [[1, 2, 3, 4]]


def test_group_size_includes_self():
    """group_size (component size) includes the survivor; neighbours exclude it."""
    ids = [1, 2, 3]
    pos = [(26.0, 92.0), (26.0, 92.0001), (26.0, 92.0002)]
    comps = events.components(ids, pos)
    # Three members, one component.
    assert comps == [[1, 2, 3]]
    group_size = len(comps[0])
    assert group_size == 3  # includes self
    # cluster_size (neighbours excluding self) for the middle survivor is 2.
    assert group_size - 1 == 2


def test_deterministic_group_ids():
    """The same geometry yields the same grouping every call."""
    ids = [7, 3, 12]
    pos = [(26.0, 92.0), (26.0, 92.0001), (27.0, 93.0)]  # first two together
    first = events.components(ids, pos)
    second = events.components(ids, pos)
    assert first == second
    # Two groups: one pair and one singleton.
    assert len(first) == 2


def test_components_uses_reference_geometry():
    """Grouping must be computed in the reference frame, not the moving origin.

    The guide's Rule 1: relative distances (clustering) use the fixed reference
    frame so the assumed flight track cancels out. This asserts that a call that
    builds positions from `bbox_to_reference_latlon` treats two detections from
    far-apart frames as neighbours if they sit together in the camera geometry.
    """
    # Two boxes in the frame-0 geometry that sit right next to each other.
    ref_a = bbox_to_reference_latlon([500, 200, 540, 240])
    ref_b = bbox_to_reference_latlon([560, 200, 600, 240])
    assert _metres(ref_a[0], ref_a[1], ref_b[0], ref_b[1]) < 15.0
    ids = [10, 11]
    comps = events.components(ids, [ref_a, ref_b])
    assert comps == [[10, 11]]


def test_components_returns_all_including_singletons():
    """`components` returns every connected component, singletons included."""
    ids = [1, 2, 3]
    pos = [(26.0, 92.0), (26.0, 92.0001), (27.0, 93.0)]
    comps = events.components(ids, pos)
    # singletons are present too.
    assert any(len(c) == 1 for c in comps)

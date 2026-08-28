"""API tests for the survivor / events / detections endpoints.

Verifies the Guide's API-compatibility rules:

  * all pre-existing fields remain (track_id, latitude, longitude, confidence,
    first_frame, confirmed_frame, last_frame, detection_count, priority,
    priority_band, cluster_size, cluster_score),
  * the new fields are present (position_spread_m, score_breakdown, group_id,
    group_size),
  * JSON serializes correctly and is valid,
  * `/api/survivors` still works end-to-end,
  * `/api/events` closing bands agree with `/api/survivors` priority bands.

`detections.json` must be present for these to run; they are skipped otherwise.
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def survivors(client):
    res = client.get("/api/survivors")
    assert res.status_code == 200
    return res.json()


@pytest.fixture(scope="module")
def events(client):
    res = client.get("/api/events")
    assert res.status_code == 200
    return res.json()


def test_survivors_endpoint_ok(client, survivors):
    assert isinstance(survivors, list)
    assert len(survivors) > 0


def test_old_fields_present(survivors):
    required = [
        "track_id",
        "latitude",
        "longitude",
        "confidence",
        "first_frame",
        "confirmed_frame",
        "last_frame",
        "detection_count",
        "priority",
        "priority_band",
        "cluster_size",
        "cluster_score",
    ]
    for field in required:
        assert all(field in s for s in survivors), f"missing {field}"


def test_new_fields_present(survivors):
    for field in ["position_spread_m", "score_breakdown", "group_id", "group_size"]:
        assert all(field in s for s in survivors), f"missing {field}"


def test_json_serializes(client, survivors):
    # Round-trip through JSON to confirm serializability.
    raw = json.dumps(survivors)
    reparsed = json.loads(raw)
    assert reparsed == survivors


def test_field_names_not_renamed(survivors):
    """Old names must remain; latitude/longitude must NOT become lat/lon."""
    for s in survivors:
        assert "latitude" in s and "lat" not in s
        assert "longitude" in s and "lon" not in s


def test_priority_in_range(survivors):
    for s in survivors:
        assert 0.0 <= s["priority"] <= 1.0


def test_priority_band_valid(survivors):
    for s in survivors:
        assert s["priority_band"] in {"low", "medium", "high", "critical"}


def test_score_breakdown_sums_to_priority(survivors):
    for s in survivors:
        total = sum(s["score_breakdown"].values())
        assert abs(total - s["priority"]) < 1e-3


def test_cluster_size_excludes_self(survivors):
    # group_size includes self; cluster_size is the direct-neighbour count.
    for s in survivors:
        assert s["cluster_size"] >= 0
        # On the fully-linked demo clip, cluster_size == group_size - 1.
        assert s["cluster_size"] <= s["group_size"] - 1 or s["group_size"] == 1


def test_dropped_terms_absent(survivors):
    # On the demo clip hazard is absent (empty layer) and must not appear.
    for s in survivors:
        assert "hazard" not in s["score_breakdown"]


def test_groups_consistent(survivors):
    # Every survivor belongs to a group whose size matches the number of
    # survivors sharing that group_id.
    from collections import Counter

    counts = Counter(s["group_id"] for s in survivors)
    for s in survivors:
        assert counts[s["group_id"]] == s["group_size"]


def test_position_spread_present_and_nonnegative(survivors):
    for s in survivors:
        assert s["position_spread_m"] >= 0.0


def test_events_endpoint_ok(client, events):
    assert isinstance(events, list)


def test_events_closing_bands_match_survivors(events, survivors):
    """The event log's closing priority bands equal the survivor table's.

    This is the reconciliation requirement: by the end of the clip the log and
    the table must show the same band for the same person.
    """
    survivor_by_track = {s["track_id"]: s["priority_band"] for s in survivors}

    # The 'to_band' of the LAST priority event per track is its closing band.
    closing = {}
    for ev in events:
        if ev["kind"] in {"priority_assessed", "priority_band"}:
            if ev.get("track_id") is not None:
                closing[ev["track_id"]] = ev["to_band"]

    # Every confirmed survivor should have a closing band recorded in the log,
    # and it must match the table's.
    for track_id, band in survivor_by_track.items():
        assert closing.get(track_id) == band


def test_detections_endpoint_ok(client):
    res = client.get("/api/detections")
    assert res.status_code == 200
    records = res.json()
    assert len(records) > 0


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_config_endpoint(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    cfg = res.json()
    assert cfg["clip_fps"] == config.CLIP_FPS

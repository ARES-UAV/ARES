"""Priority scoring tests for `backend.priority`.

Covers the three-term weighted formula, the Rule-2 drop/renormalise behaviour
(dropped terms are ABSENT from the breakdown, never present at zero), the
score_breakdown summing to the score, and the hysteresis/idempotence rules the
guide says must not be broken.
"""

import pytest

from backend import priority
from backend.priority import PriorityBreakdown, score_all


def _scores(survivors, **kwargs):
    """Small helper: score a list of (lat, lon, conf) triples."""
    return score_all(survivors, **kwargs)


def test_all_three_terms_present():
    """Different neighbour counts make the cluster term score and differentiate."""
    # A and B are ~7.8 m apart (within radius); C is ~140 m away, isolated.
    # Neighbour counts: A=1, B=1, C=0 -> the cluster term differentiates.
    survivors = [(0.0, 0.0, 0.8), (0.00007, 0.0, 0.4), (0.0009, 0.0009, 0.5)]
    results = _scores(survivors)
    breakdown = results[0].score_breakdown
    assert "confidence" in breakdown
    assert "cluster" in breakdown
    # Sum equals the score within rounding tolerance.
    assert abs(sum(breakdown.values()) - results[0].score) < 1e-3
    # The isolated survivor's count differs from the pair's, so the term is real.
    assert results[2].cluster_size == 0
    assert results[0].cluster_size == 1


def test_hazard_missing():
    """With no hazards configured, the hazard term is absent, not zero."""
    survivors = [(0.0, 0.0, 0.8), (0.01, 0.01, 0.4)]
    results = _scores(survivors)
    for result in results:
        assert result.hazard_score is None
        assert "hazard" not in result.score_breakdown


def test_cluster_missing_when_identical():
    """A cluster term identical in every row is dropped, not scored."""
    # Two survivors at the SAME position -> identical neighbour counts (1 each).
    survivors = [(0.0, 0.0, 0.8), (0.0, 0.0, 0.4)]
    results = _scores(survivors)
    for result in results:
        assert result.cluster_score is None
        assert "cluster" not in result.score_breakdown


def test_cluster_absent_single_survivor():
    """A single survivor with no neighbours -> cluster size 0, term dropped."""
    survivors = [(0.0, 0.0, 0.7)]
    results = _scores(survivors)
    result = results[0]
    assert result.cluster_size == 0
    assert result.cluster_score is None
    assert "cluster" not in result.score_breakdown


def test_renormalisation_hazard_missing():
    """Dropping hazard renormalises the remaining weights over their own sum."""
    # A and B together (~7.8 m, so 1 neighbour each); C isolated (0 neighbours).
    survivors = [(0.0, 0.0, 0.8), (0.00007, 0.0, 0.4), (0.0009, 0.0009, 0.5)]
    results = _scores(survivors)
    # Cluster is scored (counts differ: 1, 1, 0).
    wc = 0.4
    cl = 0.3
    renorm_confidence = wc / (wc + cl)
    # Survivor A has 1 neighbour -> cluster_score(1) = 1/4.
    cluster_term = min(1 / 4, 1.0)
    expect = renorm_confidence * 0.8 + (cl / (wc + cl)) * cluster_term
    assert results[0].score == pytest.approx(expect, abs=1e-3)


def test_both_hazard_and_cluster_missing_score_equals_confidence():
    """With both extra terms dropped, priority == confidence (Rule 2)."""
    survivors = [(0.0, 0.0, 0.802)]
    results = _scores(survivors)
    assert results[0].score == pytest.approx(0.802, abs=1e-4)
    assert results[0].score_breakdown == {"confidence": round(0.802, 4)}


def test_score_breakdown_sums_to_score():
    """The breakdown values sum to the priority within rounding tolerance."""
    survivors = [
        (0.0, 0.0, 0.8),
        (0.001, 0.001, 0.5),
        (0.005, 0.005, 0.3),
        (0.01, 0.01, 0.6),
    ]
    results = _scores(survivors)
    for result in results:
        assert abs(sum(result.score_breakdown.values()) - result.score) < 1e-3


def test_dropped_terms_absent_not_zero():
    """A dropped term is absent from the breakdown, never present at 0.0."""
    survivors = [(0.0, 0.0, 0.8), (0.0, 0.0, 0.4)]
    results = _scores(survivors)
    for result in results:
        assert "hazard" not in result.score_breakdown
        assert "cluster" not in result.score_breakdown
        assert result.score_breakdown.get("hazard", None) is None


def test_breakdown_deterministic():
    """Same input -> same breakdown, every call."""
    survivors = [(0.0, 0.0, 0.8), (0.01, 0.01, 0.4)]
    first = _scores(survivors)
    second = _scores(survivors)
    assert [r.score_breakdown for r in first] == [r.score_breakdown for r in second]


# ── Hysteresis and bands ────────────────────────────────────────────

def test_band_ascending():
    assert priority.band_for(0.1) == "low"
    assert priority.band_for(0.3) == "medium"
    assert priority.band_for(0.6) == "high"
    assert priority.band_for(0.8) == "critical"


def test_band_hysteresis_climb_needs_margin():
    # From "high", critical starts at 0.75 + BAND_HYSTERESIS (0.03) = 0.78.
    # 0.76 is past the raw cut but not past the margin, so it must stay high.
    assert priority.band_for(0.76, "high") == "high"
    assert priority.band_for(0.78, "high") == "critical"


def test_band_hysteresis_fall_needs_margin():
    # From "critical", falling back to "high" waits for below 0.75 - 0.03.
    assert priority.band_for(0.74, "critical") == "critical"
    assert priority.band_for(0.71, "critical") == "high"


def test_band_idempotent():
    """Re-scoring an unchanged score never moves anyone's band."""
    for score in [0.1, 0.24, 0.3, 0.49, 0.6, 0.74, 0.76, 0.8]:
        band = priority.band_for(score)
        assert priority.band_for(score, band) == band


def test_band_transitions_both_directions():
    """Transitions up and down across each cut match the hysteresis rule."""
    # Medium->high across 0.50: needs 0.53 up, drops below 0.47.
    assert priority.band_for(0.52, "medium") == "medium"
    assert priority.band_for(0.53, "medium") == "high"
    assert priority.band_for(0.48, "high") == "high"
    assert priority.band_for(0.46, "high") == "medium"


def test_hazard_score_far_below_influence():
    # Beyond HAZARD_INFLUENCE_M the term falls to 0.0 (still scored, not None).
    assert priority.hazard_score(0.0, 0.0, hazards=[(1.0, 1.0)], influence_m=50.0) == pytest.approx(0.0)


def test_hazard_score_at_hazard():
    assert priority.hazard_score(0.0, 0.0, hazards=[(0.0, 0.0)]) == pytest.approx(1.0)


def test_hazard_score_none_with_empty_layer():
    # No hazards -> None, not 0.0. "Not measured" vs "checked, nothing nearby".
    assert priority.hazard_score(0.0, 0.0, hazards=[]) is None

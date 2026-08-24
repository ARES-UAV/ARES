"""Rescue-priority scoring for located survivors.

Robin owns this module (CLAUDE.md, Team). This is the stub written from the
formula described there so the dashboard is not blocked waiting for it — swap
his version in when it is ready, keeping `score_all`'s signature.

The formula is a weighted average of three normalised 0–1 terms and nothing
cleverer, because a judge will ask how the ranking works and the answer has to
fit in one sentence:

    A survivor's priority is a weighted average of how confident the detector
    is, how many other survivors are within 15 m of them, and how close the
    nearest known hazard is — with the weights in `backend/config.py`.

Every weight, radius and threshold lives in `backend.config`, not here. This
module contains the arithmetic and no numbers.

Hazards are Phase 2. `config.HAZARDS` is empty until the hazard classifier
produces real positions, and an empty list is handled by **dropping** the
hazard term and renormalising the remaining weights — not by scoring it zero.
Those are not the same thing. A zero would read as "checked, nothing nearby"
and would pull every survivor's score down by the hazard weight, so the whole
scene would look calmer than anything anyone actually measured. Dropping it
means "not measured", which is the truth, and `PriorityBreakdown.hazard_score`
is then `None` so the dashboard can say so instead of printing a confident
0.00.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from backend import config
from backend.localize import METRES_PER_DEGREE_LAT

# One survivor's inputs: (latitude, longitude, confidence).
SurvivorPoint = Tuple[float, float, float]


@dataclass(frozen=True)
class PriorityBreakdown:
    """One survivor's score and the terms it was built from.

    The parts are kept, not just the total. The dashboard has to be able to
    answer "why is this person above that one?" without re-deriving anything,
    and a bare 0.63 cannot.
    """

    score: float
    band: str
    confidence_score: float
    cluster_score: float
    cluster_size: int
    hazard_score: Optional[float]  # None = no hazard layer, not "no hazards"


def metres_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Ground distance in metres between two nearby coordinates.

    Flat-earth, same assumption as `backend.localize` and appropriate for the
    same reason: a clip covers a few dozen metres, where the difference from a
    proper geodesic is far below the error already present in a fixed-altitude
    pixel projection. Longitude is scaled by the cosine of the mean latitude.
    """
    mean_lat = math.radians((lat1 + lat2) / 2.0)
    north_m = (lat1 - lat2) * METRES_PER_DEGREE_LAT
    east_m = (lon1 - lon2) * METRES_PER_DEGREE_LAT * math.cos(mean_lat)
    return math.hypot(north_m, east_m)


def cluster_score(neighbours: int, saturation: Optional[int] = None) -> float:
    """Normalise a neighbour count to 0–1.

    Linear up to `saturation` neighbours, flat at 1.0 above it. The ceiling is
    what stops one large group from compressing every other survivor's cluster
    term towards zero — see CLUSTER_SATURATION.
    """
    limit = config.CLUSTER_SATURATION if saturation is None else saturation
    if limit <= 0:
        return 0.0
    return min(neighbours / limit, 1.0)


def hazard_score(
    latitude: float,
    longitude: float,
    hazards: Optional[Sequence[Tuple[float, float]]] = None,
    influence_m: Optional[float] = None,
) -> Optional[float]:
    """Proximity to the nearest known hazard, 0–1, or None if there is no layer.

    1.0 at the hazard itself, falling linearly to 0.0 at `influence_m` and
    staying there. `None` is returned when no hazard positions exist at all,
    and it means "this term was not measured" — the caller must not substitute
    0.0 for it, because that claims a measurement nobody made.
    """
    known = config.HAZARDS if hazards is None else hazards
    if not known:
        return None

    reach = config.HAZARD_INFLUENCE_M if influence_m is None else influence_m
    nearest = min(
        metres_between(latitude, longitude, lat, lon) for lat, lon in known
    )
    if reach <= 0:
        return 1.0 if nearest == 0 else 0.0
    return max(0.0, 1.0 - nearest / reach)


def band_for(score: float) -> str:
    """Map a score to the dashboard's priority ramp.

    Four ordinal bands: low, medium, high, critical. They are an ORDER, not
    four statuses — the dashboard renders them as one hue darkening in four
    steps, so the ramp still reads as a ranking on a projector and to a viewer
    with a colour vision deficiency. The band name is always shown beside the
    swatch there; colour is never the only encoding.

    "low" is the bottom of the ramp, not a "clear" band. The lowest-priority
    person in a disaster zone still needs rescuing, and nothing in this ramp is
    green.

    Thresholds are the quarters of the 0-1 score range, in `backend.config`.
    This module contains the arithmetic and no numbers.
    """
    if score >= config.PRIORITY_CRITICAL_AT:
        return "critical"
    if score >= config.PRIORITY_HIGH_AT:
        return "high"
    if score >= config.PRIORITY_MEDIUM_AT:
        return "medium"
    return "low"


def score_all(survivors: Sequence[SurvivorPoint]) -> List[PriorityBreakdown]:
    """Score every survivor, returning one breakdown per input in input order.

    Batch rather than per-survivor because the cluster term is not a property
    of one person — it is how many others are near them — so a single survivor
    cannot be scored in isolation.

    The neighbour search is the naive O(n²) pass. `n` is the number of distinct
    tracks in one clip, which is tens; a spatial index here would be more code
    to get wrong for no measurable gain.

    Weights are treated as relative and divided by their own sum, so they need
    not add to 1 and — the reason it matters — dropping the hazard term when
    there is no hazard layer renormalises the remaining two instead of capping
    everyone at 0.7.
    """
    results: List[PriorityBreakdown] = []

    for index, (latitude, longitude, confidence) in enumerate(survivors):
        neighbours = 0
        for other_index, (other_lat, other_lon, _) in enumerate(survivors):
            if other_index == index:
                continue
            if (
                metres_between(latitude, longitude, other_lat, other_lon)
                <= config.CLUSTER_RADIUS_M
            ):
                neighbours += 1

        cluster = cluster_score(neighbours)
        hazard = hazard_score(latitude, longitude)

        terms = [
            (config.WEIGHT_CONFIDENCE, confidence),
            (config.WEIGHT_CLUSTER_SIZE, cluster),
        ]
        if hazard is not None:
            terms.append((config.WEIGHT_HAZARD_PROXIMITY, hazard))

        total_weight = sum(weight for weight, _ in terms)
        score = (
            sum(weight * value for weight, value in terms) / total_weight
            if total_weight > 0
            else 0.0
        )
        # Guard the range rather than trust it: a weight typed negative in
        # config would otherwise put an out-of-range score into a Pydantic
        # model and surface as a 500 from an unrelated endpoint.
        score = min(max(score, 0.0), 1.0)

        results.append(
            PriorityBreakdown(
                score=score,
                band=band_for(score),
                confidence_score=confidence,
                cluster_score=cluster,
                cluster_size=neighbours,
                hazard_score=hazard,
            )
        )

    return results

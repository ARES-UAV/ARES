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

── A term that cannot rank anything is dropped, not scored ─────────
Two of the three terms can fail to say anything about a particular clip, and
both are handled the same way: the term is **dropped** and the remaining
weights are renormalised, rather than being scored zero or left in flat.

Hazards are Phase 2. `config.HAZARDS` is empty until the hazard classifier
produces real positions. A zero there would read as "checked, nothing nearby"
and would pull every survivor's score down by the hazard weight, so the whole
scene would look calmer than anything anyone actually measured. Dropping it
means "not measured", which is the truth.

The cluster term is dropped when it comes out **identical for every survivor**
— one group with everybody inside it, or a scene so sparse that nobody has a
neighbour. A term with the same value in all 23 rows cannot rank those rows.
Leaving it in changes no ordering; it only adds a constant to everyone, which
on the current clip is a flat +0.43 that lifts the entire scene into "high"
and "critical" and makes a uniform crowd read as a uniformly severe one. What
the dashboard should say there is that cluster size did not differentiate on
this footage, which needs the term gone rather than silently inert.

In both cases the corresponding `PriorityBreakdown` field is then `None`, so
the dashboard can say "not scored" instead of printing a confident 0.00. Note
that `cluster_size` is still reported when the term is dropped: how many
survivors are nearby is an observation, and it stays true whether or not it
earned a place in the arithmetic.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

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
    # None = the term was identical for every survivor and was dropped, not
    # "nobody is nearby". `cluster_size` is reported either way.
    cluster_score: Optional[float]
    cluster_size: int
    hazard_score: Optional[float]  # None = no hazard layer, not "no hazards"
    # Each term's WEIGHTED contribution to `score`, insertion-ordered
    # (confidence, then cluster, then hazard). A dropped term is ABSENT, not
    # present at zero — see Rule 2 in the guide: a term the model never scored
    # must not read as "checked, nothing nearby". The values are the
    # renormalised weight times the term value, rounded to four decimals, so
    # they sum to `score` and the dashboard can answer "why is this person
    # above that one?" from the record alone.
    score_breakdown: Dict[str, float]


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


# The ramp, in rank order. Paired with `_band_cuts()`, whose index i is the
# score at which BANDS[i] gives way to BANDS[i + 1] — one table written as two
# sequences, so `band_for` walks it instead of repeating a comparison per band
# and the hysteresis margin is applied in one place rather than three. The cut
# values come from `backend.config`; this module still contains no numbers.
BANDS = ("low", "medium", "high", "critical")


def _band_cuts() -> Tuple[float, ...]:
    """The three thresholds, read at call time so a config edit takes effect."""
    return (
        config.PRIORITY_MEDIUM_AT,
        config.PRIORITY_HIGH_AT,
        config.PRIORITY_CRITICAL_AT,
    )


def band_for(score: float, previous: Optional[str] = None) -> str:
    """Map a score to the dashboard's priority ramp, with hysteresis.

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

    ── Hysteresis ───────────────────────────────────────────────────
    `previous` is the band this survivor is currently shown in. Given one, a
    change requires the score to clear the threshold by `BAND_HYSTERESIS`
    rather than merely reach it: from "high", "critical" starts at 0.75 + the
    margin, and from "critical", the fall back to "high" happens below
    0.75 - the margin. The bare threshold still decides where a survivor
    STARTS, which is why `previous=None` — a track being assessed for the
    first time — is scored on the cuts alone with no deadband.

    Without this a track parked near a cut does not sit in a band, it
    oscillates across one: the confidence term is the confidence of that
    track's latest detection, and that jitters frame to frame. The event log
    showed single tracks changing band five times in nine seconds, which reads
    as an unstable assessment when what is unstable is one bounding box's
    confidence. See BAND_HYSTERESIS in `backend.config` for why the margin is
    the size it is, and why it is disclosed on screen rather than applied
    quietly.

    The deadband suppresses a WOBBLE, not a move. A score that genuinely
    travels — including one that jumps two bands at once — clears the margin
    and the band follows it in the same step, because the margin is only ever
    checked against the cuts actually being crossed.

    Idempotent by construction: `band_for(s, band_for(s, p)) == band_for(s, p)`.
    Re-assessing an unchanged score never moves anyone, which is what lets
    `/api/survivors` recover the log's closing bands by re-scoring the final
    frame instead of keeping a second copy of the walk's state.
    """
    cuts = _band_cuts()

    # Where the raw thresholds alone would put this score.
    raw = 0
    for index, cut in enumerate(cuts):
        if score >= cut:
            raw = index + 1

    # No history: the thresholds are the whole rule. A first assessment has no
    # band to be sticky about.
    if previous is None or previous not in BANDS:
        return BANDS[raw]

    margin = config.BAND_HYSTERESIS
    current = BANDS.index(previous)

    # Climbing: give back each band whose cut the score has reached but not
    # cleared by the margin. Stops at `current`, so a survivor never falls
    # while moving up, and stops early on a genuine multi-band jump.
    while raw > current and score < cuts[raw - 1] + margin:
        raw -= 1

    # Falling: hold each band whose cut the score has dropped below but not by
    # the margin. Symmetric, same reason.
    while raw < current and score >= cuts[raw] - margin:
        raw += 1

    return BANDS[raw]


def score_all(
    survivors: Sequence[SurvivorPoint],
    previous_bands: Optional[Sequence[Optional[str]]] = None,
    cluster_positions: Optional[Sequence[Tuple[float, float]]] = None,
) -> List[PriorityBreakdown]:
    """Score every survivor, returning one breakdown per input in input order.

    Batch rather than per-survivor because the cluster term is not a property
    of one person — it is how many others are near them — so a single survivor
    cannot be scored in isolation.

    The neighbour search is the naive O(n²) pass. `n` is the number of distinct
    tracks in one clip, which is tens; a spatial index here would be more code
    to get wrong for no measurable gain.

    Weights are treated as relative and divided by their own sum, so they need
    not add to 1 and — the reason it matters — dropping a term that cannot rank
    anything renormalises the survivors instead of capping everyone below 1.

    :param previous_bands: the band each survivor is CURRENTLY shown in,
        positionally aligned with `survivors`, or `None` for a survivor being
        assessed for the first time. Omit the argument entirely to score with
        no history, which is the raw thresholds and no deadband — see
        `band_for`. Only the band is affected: the score itself has no memory,
        so two callers scoring the same positions always get the same number
        and can only differ in which side of a cut they choose to hold.
    :param cluster_positions: `(latitude, longitude)` per survivor, positionally
        aligned with `survivors`, giving the geometry the NEIGHBOUR COUNT is
        measured in. Defaults to the survivors' own positions.

        It is a separate argument because the two questions want different
        projections. Where a survivor is, absolutely — what the map pins and
        what a hazard distance is measured against — comes from
        `localize.bbox_to_latlon`, which advances the origin along the assumed
        flight track. How far two survivors are from EACH OTHER must not,
        because that assumption then manufactures separation out of the gap
        between their last sightings: at the configured speed a three-second
        gap invents fifteen metres between two people who may have been
        standing together. Callers pass `localize.bbox_to_reference_latlon`
        here, which holds the track still. See that function for the full
        argument; the hazard term deliberately keeps using the real positions.
    """
    if previous_bands is not None and len(previous_bands) != len(survivors):
        # Positional alignment is the whole contract of this argument, and a
        # mismatch would silently give survivor i someone else's band history.
        raise ValueError(
            f"previous_bands has {len(previous_bands)} entries for "
            f"{len(survivors)} survivors; they must align positionally"
        )

    if cluster_positions is not None and len(cluster_positions) != len(survivors):
        raise ValueError(
            f"cluster_positions has {len(cluster_positions)} entries for "
            f"{len(survivors)} survivors; they must align positionally"
        )

    # The geometry neighbours are counted in. Falling back to the survivors'
    # own positions keeps the one-argument call working; every caller in this
    # repo passes the reference-frame positions.
    geometry: List[Tuple[float, float]] = (
        [(latitude, longitude) for latitude, longitude, _ in survivors]
        if cluster_positions is None
        else list(cluster_positions)
    )

    # ── Pass one: the cluster term, before deciding whether to use it ─
    neighbour_counts: List[int] = []
    cluster_scores: List[float] = []
    for index, (latitude, longitude) in enumerate(geometry):
        neighbours = 0
        for other_index, (other_lat, other_lon) in enumerate(geometry):
            if other_index == index:
                continue
            if (
                metres_between(latitude, longitude, other_lat, other_lon)
                <= config.CLUSTER_RADIUS_M
            ):
                neighbours += 1
        neighbour_counts.append(neighbours)
        cluster_scores.append(cluster_score(neighbours))

    # A term identical in every row cannot order those rows, so it is dropped
    # and the remaining weights renormalise — see the module docstring. Exact
    # equality is the right test and not a tolerance question: these values all
    # come out of the same expression over an integer count, so equal counts
    # give bit-identical scores.
    cluster_differentiates = bool(cluster_scores) and min(cluster_scores) != max(
        cluster_scores
    )

    # ── Pass two: the score ──────────────────────────────────────────
    results: List[PriorityBreakdown] = []

    for index, (latitude, longitude, confidence) in enumerate(survivors):
        cluster = cluster_scores[index] if cluster_differentiates else None
        # Hazard proximity is measured against the survivor's REAL position,
        # not the reference-frame one: a hazard has a fixed ground position, so
        # the distance to it is an absolute question, unlike the relative one
        # the cluster term asks.
        hazard = hazard_score(latitude, longitude)

        terms = [("confidence", config.WEIGHT_CONFIDENCE, confidence)]
        if cluster is not None:
            terms.append(("cluster", config.WEIGHT_CLUSTER_SIZE, cluster))
        if hazard is not None:
            terms.append(("hazard", config.WEIGHT_HAZARD_PROXIMITY, hazard))

        total_weight = sum(weight for _, weight, _ in terms)
        score = (
            sum(weight * value for _, weight, value in terms) / total_weight
            if total_weight > 0
            else 0.0
        )
        # Guard the range rather than trust it: a weight typed negative in
        # config would otherwise put an out-of-range score into a Pydantic
        # model and surface as a 500 from an unrelated endpoint.
        score = min(max(score, 0.0), 1.0)

        # Each term's part of `score`, as the weighted contribution: the
        # renormalised weight (`weight / total_weight`) times the term value.
        # Rounded to four decimals so the record is readable; the sum stays
        # within rounding tolerance of `score` by construction, which the
        # dashboard asserts. Only the terms actually scored are listed — a
        # dropped term has no row here, matching `cluster_score`/`hazard_score`
        # being null rather than 0.0.
        score_breakdown: Dict[str, float] = {}
        for label, weight, value in terms:
            contribution = weight / total_weight * value if total_weight > 0 else 0.0
            score_breakdown[label] = round(contribution, 4)

        previous = previous_bands[index] if previous_bands is not None else None

        results.append(
            PriorityBreakdown(
                score=score,
                band=band_for(score, previous),
                confidence_score=confidence,
                cluster_score=cluster,
                cluster_size=neighbour_counts[index],
                hazard_score=hazard,
                score_breakdown=score_breakdown,
            )
        )

    return results

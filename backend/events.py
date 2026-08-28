"""The mission event timeline, derived from the clip's detection records.

The dashboard's event log is a replay of things that happened, keyed to the
same frame index every other panel is keyed on. Every line traces back to a
detection — see the demo footage policy in CLAUDE.md. Nothing in this module
authors an event, and there is no place to put one that would.

Only two kinds of event live here, because only these two cannot be derived
without `backend.localize` and `backend.priority`:

  cluster_formed   a set of survivors first seen within CLUSTER_RADIUS_M of one
                   another. Needs ground positions, so it needs the projection.

  cluster_grew     that same group, with a newly confirmed survivor in it. Split
                   from the above because one group accumulating members over a
                   clip would otherwise emit a run of `cluster_formed` lines and
                   read as many separate clusters.

  priority_band    a survivor's band, first assessed and then whenever it
                   changes. Needs the scoring formula.

Replay start, each track's first detection and the end-of-clip summary are
deliberately NOT produced here. The frontend already holds the survivor roster
and the detection index those come out of, and deriving them there means the
log's confirmation lines are the same list as the header's survivor count
rather than a second list that has to agree with it.

── How the timeline is walked ──────────────────────────────────────
Frames are visited in ascending order, and a running "latest detection per
track" table is updated as they go. At any frame, scoring that table is
*exactly* what `/api/survivors` does — same persistence filter, same
localization against that detection's own frame origin, same
`priority.score_all` — restricted to what the clip has revealed so far. So the
last frame's assessment is the survivor table's, arithmetically and not by
coincidence: walk the log to the end and the bands it leaves you with are the
bands the table shows.

That equivalence is why the persistence filter is applied HERE too rather than
only in the endpoint. A track enters the running table at the frame it is
CONFIRMED, not the frame it first appeared — see `backend.tracks`. Skipping
that would put unconfirmed flicker into the log's clusters and give it
priority bands, and the log would close on a roster the survivor table does
not have.

── Why clusters are checked every frame and priority is not ────────
They are different kinds of fact. A cluster membership is a FIRST occurrence:
each distinct set fires once ever, so re-checking every frame costs nothing
and buys exact timing. A band is a STATE that can oscillate, and re-checking
it every frame on the development fixture produces 277 changes, almost all of
them a track flickering across the 0.75 cut on detector confidence noise. That
is not a mission log, it is a stream of the same non-event. Priority is
therefore sampled — see EVENT_SAMPLE_INTERVAL_S in `backend.config` for the
full argument and what the sampling does and does not hide.

Sampling alone was not enough. It sets how often the question is asked; it
does nothing about the answer flipping between two consecutive asks, and the
log still showed single tracks changing band five times in nine seconds. The
band is therefore also hysteretic: the walk feeds each track's currently
reported band back into the next assessment, and `priority.band_for` requires
the score to clear the cut by BAND_HYSTERESIS before it moves. The two levers
are independent and both are disclosed on the dashboard.
"""

from typing import Dict, List, Sequence, Tuple

from backend import config, localize, priority, tracks
from backend.schemas import Detection, MissionEvent

# One entry of the running table: the most recent detection seen for a track.
LatestByTrack = Dict[int, Detection]


def _sample_interval_frames() -> int:
    """The priority sampling interval, in frames.

    At least 1: a configured interval shorter than a frame cannot mean
    anything finer than every frame, and 0 would mean never.
    """
    return max(1, round(config.EVENT_SAMPLE_INTERVAL_S * config.CLIP_FPS))


def _positions(latest: LatestByTrack, track_ids: Sequence[int]) -> List[Tuple[float, float, float]]:
    """Ground positions and confidences for the roster, in `track_ids` order.

    Each track is localized against the origin for the frame ITS OWN latest
    detection came from, not the frame currently being walked. The drone is
    assumed to be moving, so a track last seen forty frames ago was last seen
    somewhere the drone has since flown past — using the current frame's origin
    would drag every stale track along with the aircraft.

    This is the same call `/api/survivors` makes, which is what makes the two
    converge at the end of the clip.
    """
    positions = []
    for track_id in track_ids:
        detection = latest[track_id]
        latitude, longitude = localize.bbox_to_latlon(
            detection.bbox, detection.frame_id
        )
        positions.append((latitude, longitude, detection.confidence))
    return positions


def _cluster_positions(
    latest: LatestByTrack, track_ids: Sequence[int]
) -> List[Tuple[float, float]]:
    """The same roster in the geometry RELATIVE distance is measured in.

    Every track localized against one reference frame instead of its own, so
    the assumed flight track cancels out of the distance between two of them —
    see `localize.bbox_to_reference_latlon` for why that assumption has to be
    kept out of any relative measurement.

    Both things in this module that ask how far apart two survivors are use
    this rather than `_positions`: the cluster term inside `priority.score_all`
    and the `cluster_formed` events below. They are two readings of one
    geometry and would stop being that if they were taken in different frames.
    `_positions` remains what a position IS, which is what the map plots and
    what a hazard distance is measured against.
    """
    return [
        localize.bbox_to_reference_latlon(latest[track_id].bbox)
        for track_id in track_ids
    ]


def components(
    track_ids: Sequence[int],
    positions: Sequence[Tuple[float, float]],
) -> List[List[int]]:
    """Connected components of survivors, linked by the cluster radius.

    Single-linkage connected components under the *same* relation
    `priority.score_all` counts neighbours with — "within CLUSTER_RADIUS_M" —
    in the *same* reference-frame geometry (`_cluster_positions`), so the
    membership, the `cluster_size` in the survivor table and the `group_size`
    added per survivor are three readings of one geometry rather than three
    definitions of the word.

    Every survivor belongs to exactly one component, so this returns ALL of
    them, including singletons (a component of one — `group_size` 1). That is
    what distinguishes it from `_clusters`, which returns only components of
    two or more because the event log has nothing to say about a person alone.
    The two are different views of the same parts: filtering the output here
    on `len(members) >= 2` is exactly `_clusters`.

    The returned list is sorted by smallest member, and each component's
    members ascending, so the same clip yields the same grouping every call —
    a reload must not reshuffle which people share a group.

    O(n²), like the scoring pass and for the same reason: `n` is the number of
    distinct tracks in one clip, which is tens.
    """
    count = len(track_ids)
    parent = list(range(count))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]  # path halving
            node = parent[node]
        return node

    for i in range(count):
        for j in range(i + 1, count):
            distance = priority.metres_between(
                positions[i][0], positions[i][1], positions[j][0], positions[j][1]
            )
            if distance <= config.CLUSTER_RADIUS_M:
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_i] = root_j

    groups: Dict[int, List[int]] = {}
    for i in range(count):
        groups.setdefault(find(i), []).append(track_ids[i])

    # `sorted` on the group lists sorts by first (smallest) member, then by
    # length — a stable total order the same geometry always lands in.
    return sorted(sorted(members) for members in groups.values())


def _clusters(
    track_ids: Sequence[int],
    positions: Sequence[Tuple[float, float]],
) -> List[List[int]]:
    """Groups of two or more survivors linked by the cluster radius.

    Components of exactly one survivor have nothing to say in the event log —
    "a person is alone" is not a cluster-forming event — so they are dropped
    here. Every component of any size is in `components`; this is that set
    with the singletons filtered out, and nothing else differs.

    They are not the same number and are not meant to be: `cluster_size` is one
    survivor's direct neighbour count, while a component is the whole group
    that count belongs to. A chain of people 14 m apart is one cluster here and
    two neighbours each in the table, and both statements are true.
    """
    return [
        members
        for members in components(track_ids, positions)
        if len(members) >= 2
    ]


def _walk(detections: Sequence[Detection]) -> Tuple[List[MissionEvent], Dict[int, str]]:
    """Walk the clip once, returning its timeline and its closing band state.

    The single implementation behind `derive_events` and `final_bands`. Both
    outputs fall out of one pass and neither can be produced without it — the
    events because they are the pass, the closing bands because hysteresis
    makes a band depend on the history that reached it.

    Two kinds of detection take no part, for two different reasons.

    Untracked ones (`track_id == -1`) have no identity: they are real
    detections and the video overlay draws them, but two of them may be one
    person, so they cannot be placed in a cluster or given a priority without
    inventing an identity for them.

    Unconfirmed ones have an identity that has not yet earned a place on the
    roster. A track joins the walk at the frame it reaches the persistence
    threshold and is invisible to the log before then, so a two-frame flicker
    never forms a cluster and never gets a priority band. This is the same
    filter `/api/survivors` applies, from the same `backend.tracks` rule, which
    is what keeps the log's closing assessment equal to the table's.

    :param detections: every record for the clip, in any order
    :returns: `(events, final_bands)` — events sorted by frame, then by kind,
        then by track; and the band each confirmed track is left in at the end
        of the walk, keyed by `track_id`.
    """
    confirmed_at = tracks.confirmation_frames(detections)

    by_frame: Dict[int, List[Detection]] = {}
    for detection in detections:
        # Membership of `confirmed_at` is the roster test; its value is when
        # the track joined it. A detection from before that frame is evidence
        # the track was still accumulating, not a survivor sighting.
        confirmation_frame = confirmed_at.get(detection.track_id)
        if confirmation_frame is None or detection.frame_id < confirmation_frame:
            continue
        by_frame.setdefault(detection.frame_id, []).append(detection)

    if not by_frame:
        return [], {}

    frames = sorted(by_frame)
    final_frame = frames[-1]
    interval = _sample_interval_frames()

    latest: LatestByTrack = {}
    last_band: Dict[int, str] = {}
    seen_clusters: set = set()
    next_sample_frame = frames[0]
    events: List[MissionEvent] = []

    for frame_id in frames:
        # A track appearing in `latest` for the first time is a track being
        # CONFIRMED, not first detected — `by_frame` above dropped everything
        # earlier than its confirmation frame.
        confirmed_here = False
        for detection in by_frame[frame_id]:
            if detection.track_id not in latest:
                confirmed_here = True
            latest[detection.track_id] = detection

        track_ids = sorted(latest)
        positions = _positions(latest, track_ids)
        cluster_geometry = _cluster_positions(latest, track_ids)

        # ── Clusters: every frame, each membership set once ──────────
        #
        # A membership set that is a strict SUPERSET of one already reported is
        # the same group with someone new in it, not a second group. The
        # distinction is the whole reason there are two kinds here: on the demo
        # clip every survivor ends up inside one 11 m patch, so nineteen
        # distinct membership sets are emitted and all nineteen describe one
        # group growing 2 -> 23. Reporting each of them as a cluster FORMING
        # reads as nineteen clusters, which is a straight contradiction of the
        # panel next to it saying there is one group.
        #
        # Why the group grows at all is worth knowing, because it is not what
        # the word suggests: nobody walks together. A track joins the roster at
        # the frame it is CONFIRMED (see `backend.tracks`), so the membership
        # curve is the confirmation curve. "Grew" here means the system found
        # another member of a group that was always there.
        for members in _clusters(track_ids, cluster_geometry):
            key = frozenset(members)
            if key in seen_clusters:
                continue
            # `>` is strict superset on a frozenset. Checked against every set
            # already reported rather than only the last one, because two
            # groups can grow independently before merging.
            grew = any(key > reported for reported in seen_clusters)
            seen_clusters.add(key)
            events.append(
                MissionEvent(
                    frame_id=frame_id,
                    kind="cluster_grew" if grew else "cluster_formed",
                    track_ids=members,
                )
            )

        # ── Priority: sampled, plus every roster change and the end ──
        # A newly confirmed track is forced through because adding one to the
        # roster is the single thing that provably moves every other survivor's
        # cluster term, and the log should attribute the escalation to it
        # rather than report it up to a second later next to nothing.
        #
        # The final frame is forced through so the timeline closes on the same
        # assessment `/api/survivors` gives the table.
        due = frame_id >= next_sample_frame or confirmed_here or frame_id == final_frame
        if not due:
            continue
        next_sample_frame = frame_id + interval

        # `last_band` is both the change test and the hysteresis input, and it
        # has to be both. The band a track is HELD in is the band it was last
        # reported in, so scoring against anything else — the raw thresholds,
        # or the band the previous sample would have given without a deadband —
        # would let a track drift band without the log ever saying it moved.
        previously = [last_band.get(track_id) for track_id in track_ids]

        for track_id, breakdown in zip(
            track_ids, priority.score_all(positions, previously, cluster_geometry)
        ):
            previous = last_band.get(track_id)
            if previous == breakdown.band:
                continue
            last_band[track_id] = breakdown.band
            events.append(
                MissionEvent(
                    frame_id=frame_id,
                    kind="priority_band",
                    track_id=track_id,
                    # None on a track's first assessment. The dashboard renders
                    # that as "assessed", not as a change from nothing.
                    from_band=previous,
                    to_band=breakdown.band,
                    score=breakdown.score,
                )
            )

    # Frame order first. Within a frame, clusters before priority, because a
    # cluster forming is what moved the score that the band change reports —
    # the log should read in the order the causation ran.
    # Both cluster kinds share rank 0: they are the same class of fact about
    # the same geometry, and a growth line and a formation line never land on
    # one frame anyway.
    kind_rank = {"cluster_formed": 0, "cluster_grew": 0, "priority_band": 1}
    events.sort(
        key=lambda e: (e.frame_id, kind_rank[e.kind], e.track_id or 0)
    )
    return events, last_band


def derive_events(detections: Sequence[Detection]) -> List[MissionEvent]:
    """The clip's mission event timeline, in frame order.

    What `/api/events` serves. See `_walk` for what is in it and what is not.
    """
    return _walk(detections)[0]


def final_bands(detections: Sequence[Detection]) -> Dict[int, str]:
    """The band each confirmed track is left in at the end of the clip.

    `/api/survivors` needs this because hysteresis gave the band a memory. A
    score still says everything about itself, but which side of a cut that
    score is HELD on depends on where the track came from, and the endpoint
    scores one frame rather than walking to it — on its own it would put a
    survivor sitting at 0.76 in "critical" while the log, which watched them
    arrive there from below, still has them in "high". Same clip, same number,
    two answers on screen at once. That is precisely the reconciliation failure
    CLAUDE.md's dashboard requirements open with, so the endpoint takes its
    history from the same walk the log does instead of inventing one.

    Tracks absent from the returned mapping have no assessment yet and should
    be scored with no previous band — the raw thresholds, no deadband.

    Cheap enough to call per request: the walk is O(frames x tracks²) on a
    roster of tens and measures in hundredths of a second on the demo clip,
    against a detections file that is re-read from disk on every request
    anyway.
    """
    return _walk(detections)[1]

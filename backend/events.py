"""The mission event timeline, derived from the clip's detection records.

The dashboard's event log is a replay of things that happened, keyed to the
same frame index every other panel is keyed on. Every line traces back to a
detection — see the demo footage policy in CLAUDE.md. Nothing in this module
authors an event, and there is no place to put one that would.

Only two kinds of event live here, because only these two cannot be derived
without `backend.localize` and `backend.priority`:

  cluster_formed   a set of survivors first seen within CLUSTER_RADIUS_M of one
                   another. Needs ground positions, so it needs the projection.

  priority_band    a survivor's band, first assessed and then whenever it
                   changes. Needs the scoring formula.

Replay start, each track's first detection and the end-of-clip summary are
deliberately NOT produced here. The frontend already holds the survivor roster
and the detection index those come out of, and deriving them there means the
log's acquisition lines are the same list as the header's survivor count
rather than a second list that has to agree with it.

── How the timeline is walked ──────────────────────────────────────
Frames are visited in ascending order, and a running "latest detection per
track" table is updated as they go. At any frame, scoring that table is
*exactly* what `/api/survivors` does — same localization against that
detection's own frame origin, same `priority.score_all` — restricted to what
the clip has revealed so far. So the last frame's assessment is the survivor
table's, arithmetically and not by coincidence: walk the log to the end and
the bands it leaves you with are the bands the table shows.

── Why clusters are checked every frame and priority is not ────────
They are different kinds of fact. A cluster membership is a FIRST occurrence:
each distinct set fires once ever, so re-checking every frame costs nothing
and buys exact timing. A band is a STATE that can oscillate, and re-checking
it every frame on the development fixture produces 277 changes, almost all of
them a track flickering across the 0.75 cut on detector confidence noise. That
is not a mission log, it is a stream of the same non-event. Priority is
therefore sampled — see EVENT_SAMPLE_INTERVAL_S in `backend.config` for the
full argument and what the sampling does and does not hide.
"""

from typing import Dict, List, Sequence, Tuple

from backend import config, localize, priority
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


def _clusters(
    track_ids: Sequence[int],
    positions: Sequence[Tuple[float, float, float]],
) -> List[List[int]]:
    """Groups of two or more survivors linked by the cluster radius.

    Single-linkage connected components under the *same* relation
    `priority.score_all` counts neighbours with — "within CLUSTER_RADIUS_M" —
    so a cluster on the event log and a `cluster_size` in the survivor table
    are two readings of one geometry rather than two definitions of the word.

    They are not the same number and are not meant to be: `cluster_size` is one
    survivor's direct neighbour count, while a component is the whole group
    that count belongs to. A chain of people 14 m apart is one cluster here and
    two neighbours each in the table, and both statements are true.

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

    # Sorted membership, sorted groups: the same clip must produce the same
    # log line in the same order on every request, or a judge who reloads the
    # dashboard sees the timeline reshuffle itself.
    return sorted(
        (sorted(members) for members in groups.values() if len(members) >= 2)
    )


def derive_events(detections: Sequence[Detection]) -> List[MissionEvent]:
    """Walk the clip and return its event timeline, in frame order.

    Untracked detections (`track_id == -1`) take no part. They are real
    detections and the video overlay draws them, but two of them may be one
    person, so they cannot be placed in a cluster or given a priority without
    inventing an identity for them.

    :param detections: every record for the clip, in any order
    :returns: events sorted by frame, then by kind, then by track
    """
    by_frame: Dict[int, List[Detection]] = {}
    for detection in detections:
        if detection.track_id < 0:
            continue
        by_frame.setdefault(detection.frame_id, []).append(detection)

    if not by_frame:
        return []

    frames = sorted(by_frame)
    final_frame = frames[-1]
    interval = _sample_interval_frames()

    latest: LatestByTrack = {}
    last_band: Dict[int, str] = {}
    seen_clusters: set = set()
    next_sample_frame = frames[0]
    events: List[MissionEvent] = []

    for frame_id in frames:
        acquired_here = False
        for detection in by_frame[frame_id]:
            if detection.track_id not in latest:
                acquired_here = True
            latest[detection.track_id] = detection

        track_ids = sorted(latest)
        positions = _positions(latest, track_ids)

        # ── Clusters: every frame, each membership set once ──────────
        for members in _clusters(track_ids, positions):
            key = frozenset(members)
            if key in seen_clusters:
                continue
            seen_clusters.add(key)
            events.append(
                MissionEvent(
                    frame_id=frame_id, kind="cluster_formed", track_ids=members
                )
            )

        # ── Priority: sampled, plus every roster change and the end ──
        # A new track is forced through because acquiring one is the single
        # thing that provably moves every other survivor's cluster term, and
        # the log should attribute the escalation to it rather than report it
        # up to a second later next to nothing.
        #
        # The final frame is forced through so the timeline closes on the same
        # assessment `/api/survivors` gives the table.
        due = frame_id >= next_sample_frame or acquired_here or frame_id == final_frame
        if not due:
            continue
        next_sample_frame = frame_id + interval

        for track_id, breakdown in zip(track_ids, priority.score_all(positions)):
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
    kind_rank = {"cluster_formed": 0, "priority_band": 1}
    events.sort(
        key=lambda e: (e.frame_id, kind_rank[e.kind], e.track_id or 0)
    )
    return events

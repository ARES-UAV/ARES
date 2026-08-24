/**
 * The mission event log's entries, assembled from state the dashboard already
 * holds.
 *
 * Two sources meet here and the split between them is deliberate:
 *
 *   FROM THE BACKEND (`/api/events`) — cluster formation and priority bands.
 *                    Both need ground positions and the scoring formula, and
 *                    those live server-side in `backend.localize` and
 *                    `backend.priority`. The frontend never recomputes a
 *                    position or a score; it renders the ones it is given.
 *
 *   FROM SHARED STATE — replay start, each track's first detection, and the
 *                    end-of-clip summary. These are derived HERE, from the
 *                    same survivor roster the header counts and the table
 *                    renders.
 *
 * That second half is not an oversight, it is the point. The obvious design
 * has the backend emit an acquisition event per track, and then the log's
 * acquisition lines are a second list of survivors that has to agree with the
 * header's count. CLAUDE.md's first dashboard requirement is that counts
 * reconcile, and the standing rule in this codebase is that agreeing is not
 * the same as being one number. So the acquisition lines ARE the roster: one
 * line per element of the same array `survivorsInClip` is the length of. They
 * cannot disagree, because there is nothing to disagree.
 *
 * Nothing in this module authors an event. Every line traces to a detection
 * record — see the demo footage policy in CLAUDE.md. There is deliberately no
 * "system ready" or "scanning sector 4" line, because there is no scan and no
 * sector, and a log that mixes real events with atmosphere is a log a judge
 * cannot trust any line of.
 */

import { detectionsAt } from './detectionIndex.js'

/**
 * Sort rank within a single frame.
 *
 * Several things can land on one frame, and the order they are read in should
 * be the order the causation ran: a track is acquired, that acquisition puts
 * it in a cluster, and being in a cluster is what moved the priority score the
 * band line reports. Reading the consequence above its cause makes the log
 * look arbitrary.
 */
const KIND_RANK = {
  replay_start: 0,
  track_acquired: 1,
  cluster_formed: 2,
  priority_assessed: 3,
  priority_changed: 3,
  clip_end: 4,
}

/**
 * @typedef {object} LogEntry
 * @property {string} id            stable React key
 * @property {number} frame         frame the event happened on
 * @property {string} kind          a key of KIND_RANK
 * @property {number} [trackId]
 * @property {number[]} [trackIds]  cluster membership
 * @property {number|null} [confidence]
 * @property {string} [fromBand]
 * @property {string} [toBand]
 * @property {number} [score]
 */

/**
 * Build the whole clip's log, in the order it should be read.
 *
 * The result is the WHOLE clip, not the part played so far. Filtering to the
 * playback position is the panel's job and it is one comparison — building the
 * list again on every frame would rebuild forty entries twenty-four times a
 * second to change which of them are visible.
 *
 * @param {object} params
 * @param {object[]|null} params.events    `/api/events` payload, or null
 * @param {object[]|null} params.survivors the survivor roster, or null
 * @param {object} params.index            the detection index
 * @param {number} params.lastFrame        final frame of the clip
 * @returns {LogEntry[]}
 */
export function buildMissionLog({ events, survivors, index, lastFrame }) {
  const entries = []

  // Frame 0 always, even before anything has loaded. The log should say the
  // replay started rather than sit empty and look broken.
  entries.push({ id: 'replay-start', frame: 0, kind: 'replay_start' })

  // ── One line per survivor, from the roster ───────────────────────
  // `first_frame` is the roster's own record of when the track was first seen,
  // so this loop cannot discover a survivor the table does not have or miss
  // one it does.
  //
  // The confidence is looked up in the detection index at that frame — the
  // roster carries the confidence of each track's LATEST detection, which is
  // not what a first-sighting line should quote. A missing lookup renders
  // without a figure rather than substituting the one that is to hand: they
  // are different measurements and only one of them is the first sighting.
  for (const survivor of survivors ?? []) {
    const first = detectionsAt(index, survivor.first_frame).find(
      (d) => d.track_id === survivor.track_id,
    )
    entries.push({
      id: `acquired-${survivor.track_id}`,
      frame: survivor.first_frame,
      kind: 'track_acquired',
      trackId: survivor.track_id,
      confidence: first ? first.confidence : null,
    })
  }

  // ── The backend's timeline ───────────────────────────────────────
  for (const event of events ?? []) {
    if (event.kind === 'cluster_formed') {
      entries.push({
        id: `cluster-${event.frame_id}-${event.track_ids.join('-')}`,
        frame: event.frame_id,
        kind: 'cluster_formed',
        trackIds: event.track_ids,
      })
    } else if (event.kind === 'priority_band') {
      // A null `from_band` is a track's FIRST assessment, not a change from
      // nothing. The two read differently and are rendered differently.
      const assessed = event.from_band == null
      entries.push({
        id: `band-${event.frame_id}-${event.track_id}`,
        frame: event.frame_id,
        kind: assessed ? 'priority_assessed' : 'priority_changed',
        trackId: event.track_id,
        fromBand: event.from_band ?? undefined,
        toBand: event.to_band,
        score: event.score,
      })
    }
  }

  // ── The closing summary ──────────────────────────────────────────
  // At the clip's last frame, which comes from the video's true duration —
  // NOT from the last frame carrying a detection. Footage usually runs on
  // after the last person leaves the frame, and a summary that fired early
  // would claim the clip ended while it was visibly still playing.
  if (Number.isFinite(lastFrame) && lastFrame > 0) {
    entries.push({ id: 'clip-end', frame: lastFrame, kind: 'clip_end' })
  }

  entries.sort(
    (a, b) =>
      a.frame - b.frame ||
      KIND_RANK[a.kind] - KIND_RANK[b.kind] ||
      (a.trackId ?? 0) - (b.trackId ?? 0),
  )
  return entries
}

/**
 * The entries visible at a playback instant.
 *
 * Everything at or before the current frame, and nothing after it. That single
 * rule is what makes scrubbing work in both directions with no second code
 * path: drag backwards and the later lines are simply no longer included, so
 * the log always describes the frame on screen rather than accumulating a
 * history of a playhead that has since moved.
 *
 * @param {LogEntry[]} entries
 * @param {number} frame
 * @returns {LogEntry[]}
 */
export function entriesThrough(entries, frame) {
  // Entries are frame-sorted, so the visible set is a prefix — find where it
  // ends rather than testing all of them on every one of 24 frames a second.
  let end = 0
  while (end < entries.length && entries[end].frame <= frame) end += 1
  return end === entries.length ? entries : entries.slice(0, end)
}

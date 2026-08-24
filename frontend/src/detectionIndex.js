/**
 * Derived views over the clip's detection records.
 *
 * Everything the dashboard counts from raw detections is computed here, once,
 * from the single `detections` array App holds. CLAUDE.md's first dashboard
 * requirement is that counts reconcile across every section, and the way that
 * is guaranteed is that no panel is allowed to count anything for itself — the
 * header and the video overlay both read the structures below, so "3 in frame"
 * in the header and three boxes on the video are the same lookup, not two
 * agreeing calculations.
 *
 * ── Two of the header's three counts come from here, and the third
 *    deliberately does not ─────────────────────────────────────────────
 * This module used to be forbidden from tallying track IDs at all, because
 * back then a distinct-track-ID count and the length of the `/api/survivors`
 * list were two ways of answering one question, and two ways of answering one
 * question is exactly the flaw the requirement exists to prevent.
 *
 * Persistence filtering separates them into two different questions, and the
 * distance between the answers is the point:
 *
 *   raw detections    every box the model drew on this frame. `byFrame`.
 *   unique track IDs  every identity the tracker has issued so far.
 *                     `trackStarts` / `uniqueTracksThrough`. Includes flicker
 *                     and ID switches — it is what the tracker output looks
 *                     like BEFORE the filter.
 *   confirmed         the tracks that persisted for MIN_TRACK_SECONDS. NOT
 *   survivors         here and never will be: it is the length of the array
 *                     the survivor table renders as rows, so the header figure
 *                     and the row count are one value rather than two.
 *
 * The first two are counted here because both are readings of the raw file and
 * neither is a survivor count. The third is the survivor count, so it stays
 * where the survivors are. All three descend from the same detections array —
 * `/api/survivors` is a server-side view of the very file this index is built
 * from — which is what makes the gap between the last two a fact about the
 * data rather than a discrepancy between two tallies.
 */

/**
 * @typedef {object} DetectionIndex
 * @property {Map<number, object[]>} byFrame        detections keyed by frame_id
 * @property {number[]} trackStarts                 each track's first frame, ascending
 * @property {number} trackCount                    distinct track IDs in the clip
 * @property {number} maxFrame                      highest frame_id present
 * @property {number} totalDetections               raw record count
 */

/**
 * Build every derived count the dashboard needs in one pass.
 *
 * @param {object[]} detections records matching the CLAUDE.md JSON contract
 * @returns {DetectionIndex}
 */
export function buildDetectionIndex(detections) {
  const byFrame = new Map()
  const firstFrameByTrack = new Map()
  let maxFrame = 0

  for (const detection of detections) {
    const frame = detection.frame_id
    if (frame > maxFrame) maxFrame = frame
    const existing = byFrame.get(frame)
    if (existing) existing.push(detection)
    else byFrame.set(frame, [detection])

    // -1 is the tracker declining to assign an ID. Two untracked boxes may be
    // one person, so they have no identity to count — they are in the raw
    // per-frame figure and nowhere else.
    const trackId = detection.track_id
    if (trackId < 0) continue
    const seen = firstFrameByTrack.get(trackId)
    if (seen === undefined || frame < seen) firstFrameByTrack.set(trackId, frame)
  }

  // Just the frames, sorted. The IDs themselves are never needed for a count,
  // and a sorted array of start frames answers "how many by frame N?" with a
  // binary search instead of a scan of every track on every one of 24 frames
  // a second.
  const trackStarts = [...firstFrameByTrack.values()].sort((a, b) => a - b)

  return {
    byFrame,
    trackStarts,
    trackCount: trackStarts.length,
    maxFrame,
    totalDetections: detections.length,
  }
}

/**
 * Raw detection records the model emitted for exactly this frame.
 *
 * Not clamped: a frame with no detections genuinely has none, and showing 0 is
 * the truth. Returns a shared empty array — do not mutate the result.
 *
 * @param {DetectionIndex} index
 * @param {number} frame
 * @returns {object[]}
 */
const NO_DETECTIONS = []
export function detectionsAt(index, frame) {
  return index.byFrame.get(frame) ?? NO_DETECTIONS
}

/**
 * How many distinct track IDs the tracker has issued by this frame.
 *
 * The RAW tracker output, before persistence filtering — deliberately not a
 * survivor count, and the header labels it as what it is. On the current clip
 * it ends at 333 against 23 confirmed survivors, and that gap is the price of
 * a 0.18 confidence threshold rather than a bug in either number.
 *
 * @param {DetectionIndex} index
 * @param {number} frame
 * @returns {number}
 */
export function uniqueTracksThrough(index, frame) {
  // Upper bound over the ascending start frames: the number of tracks whose
  // first sighting is at or before `frame`.
  const starts = index.trackStarts
  let low = 0
  let high = starts.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (starts[mid] <= frame) low = mid + 1
    else high = mid
  }
  return low
}

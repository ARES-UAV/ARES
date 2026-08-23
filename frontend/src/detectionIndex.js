/**
 * Derived views over the clip's detection records.
 *
 * Everything the dashboard counts is computed here, once, from the single
 * `detections` array App holds. CLAUDE.md's first dashboard requirement is that
 * counts reconcile across every section, and the way that is guaranteed is that
 * no panel is allowed to count anything for itself — the header and the video
 * overlay both read the structures below, so "3 in frame" in the header and
 * three boxes on the video are the same lookup, not two agreeing calculations.
 */

/**
 * @typedef {object} DetectionIndex
 * @property {Map<number, object[]>} byFrame        detections keyed by frame_id
 * @property {Int32Array} uniqueTracksThrough       distinct track_ids seen from
 *                                                  frame 0 through frame i
 * @property {number} maxFrame                      highest frame_id present
 * @property {number} totalUniqueTracks             distinct track_ids in the clip
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
  let maxFrame = 0

  for (const detection of detections) {
    const frame = detection.frame_id
    if (frame > maxFrame) maxFrame = frame
    const existing = byFrame.get(frame)
    if (existing) existing.push(detection)
    else byFrame.set(frame, [detection])
  }

  // Cumulative distinct track_ids, so the header can answer "how many separate
  // people has the drone found *so far*" at any point in playback without
  // rescanning the clip on every frame. A dense array costs 4 bytes per frame
  // and turns the per-frame question into one indexed read.
  //
  // track_id -1 means the tracker assigned no ID. Those detections are real and
  // are drawn on the video, but they cannot be de-duplicated — two -1s might be
  // one person seen twice — so counting them would inflate the survivor number.
  // They are excluded here and everywhere else the count is derived.
  const seen = new Set()
  const uniqueTracksThrough = new Int32Array(maxFrame + 1)

  for (let frame = 0; frame <= maxFrame; frame += 1) {
    for (const detection of byFrame.get(frame) ?? []) {
      if (detection.track_id !== -1) seen.add(detection.track_id)
    }
    uniqueTracksThrough[frame] = seen.size
  }

  return {
    byFrame,
    uniqueTracksThrough,
    maxFrame,
    totalUniqueTracks: seen.size,
    totalDetections: detections.length,
  }
}

/**
 * Distinct survivors tracked from the start of the clip up to `frame`.
 *
 * The playback clock can run past the last detection — the video may be longer
 * than the processed range, and a paused video sitting on the final frame is
 * normal — so the frame is clamped rather than returning 0 off the end.
 *
 * @param {DetectionIndex} index
 * @param {number} frame
 * @returns {number}
 */
export function uniqueTracksAt(index, frame) {
  if (index.maxFrame < 0 || index.uniqueTracksThrough.length === 0) return 0
  const clamped = Math.min(Math.max(frame, 0), index.maxFrame)
  return index.uniqueTracksThrough[clamped]
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

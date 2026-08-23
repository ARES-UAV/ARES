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
 * SURVIVOR counts deliberately do not live here. This module used to tally
 * distinct track_ids as well, which gave the dashboard two ways to answer "how
 * many survivors?" — this one, and the length of the `/api/survivors` list the
 * map and the table render. The two agreed, because both descend from the same
 * detections file, but agreeing is not the same as being one number, and the
 * header's figure now has to equal the table's row count exactly. So the
 * survivor roster is the single source for that and this module counts frames.
 */

/**
 * @typedef {object} DetectionIndex
 * @property {Map<number, object[]>} byFrame        detections keyed by frame_id
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
  let maxFrame = 0

  for (const detection of detections) {
    const frame = detection.frame_id
    if (frame > maxFrame) maxFrame = frame
    const existing = byFrame.get(frame)
    if (existing) existing.push(detection)
    else byFrame.set(frame, [detection])
  }

  return {
    byFrame,
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

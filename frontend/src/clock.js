/**
 * Readings of the playback clock.
 *
 * The dashboard has one clock — `currentFrame` in App — and two things render
 * it as a time: the video panel's counter and the mission event log's
 * timestamps. Both go through here, so a frame shown as 00:12.4 under the
 * video is 00:12.4 in the log, and a change to the format is one edit.
 *
 * These are readings of the CLIP, never of the wall clock. The demo replays a
 * stored file; `new Date()` has nothing to do with where the drone was, and a
 * log stamped with the time the browser happened to render it would be
 * unreadable next to a frame index and useless when the clip is scrubbed.
 */

/** How many frames per second when the clip's declared rate is unusable. */
const FALLBACK_FPS = 1

/**
 * mm:ss.d — minutes, seconds, tenths.
 *
 * Tenths because the clip is seconds long: whole seconds would put a dozen log
 * lines on the same stamp, and hundredths would be a precision the frame index
 * beside it already carries better.
 *
 * Returns a same-width placeholder rather than throwing or rendering NaN. A
 * timestamp column that changes width as values arrive makes the whole log
 * shuffle sideways.
 *
 * @param {number} seconds
 * @returns {string}
 */
export function timecode(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '--:--.-'
  const whole = Math.floor(seconds)
  const mm = String(Math.floor(whole / 60)).padStart(2, '0')
  const ss = String(whole % 60).padStart(2, '0')
  return `${mm}:${ss}.${Math.floor((seconds - whole) * 10)}`
}

/**
 * mm:ss.d for a frame index, at the clip's declared rate.
 *
 * The frame is the source of truth on this dashboard and the timecode is its
 * human reading, which is why the conversion runs in this direction and never
 * the other. `fps` is the DECLARED clip rate from config — browsers expose no
 * way to measure a video's true frame rate — so this inherits whatever error
 * that declaration carries, the same error the frame index itself carries.
 *
 * @param {number} frame
 * @param {number} fps declared clip frame rate
 * @returns {string}
 */
export function frameTimecode(frame, fps) {
  const rate = Number.isFinite(fps) && fps > 0 ? fps : FALLBACK_FPS
  return timecode(frame / rate)
}

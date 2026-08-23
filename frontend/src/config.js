/**
 * Tunable constants for the dashboard frontend.
 *
 * Mirrors the intent of `backend/config.py`: anything a judge might ask "where
 * does that number come from?" about lives in one place, not scattered through
 * components.
 */

/**
 * Frame rate of the demo clip.
 *
 * Browsers expose no API for a video's true frame rate — `HTMLVideoElement`
 * has duration and currentTime and nothing else — so it has to be declared
 * here rather than measured. `demo_clip.mp4` is 23.976 fps (24000/1001, the
 * usual NTSC film rate); 24 is close enough that the derived frame index does
 * not drift by a whole frame across the 27-second clip.
 *
 * If the clip is replaced, this must be updated by hand or every overlay will
 * be drawn against the wrong frame.
 */
export const FPS = 24

/**
 * The resolution the detection bboxes are expressed in.
 *
 * This is the coordinate space of the frames the model ran on, which is NOT
 * necessarily the resolution of the video file being played — demo_clip.mp4 is
 * actually 1280x676. Bounding boxes must be scaled from these dimensions to
 * whatever size the video element is displayed at; never from the video
 * element's own videoWidth/videoHeight.
 */
export const SOURCE_WIDTH = 1280
export const SOURCE_HEIGHT = 720

/**
 * Where the browser loads the clip from.
 *
 * Served out of `frontend/public/`, not the backend, so the video panel still
 * works with the backend switched off (CLAUDE.md, demo-day constraint 2).
 */
export const CLIP_SRC = '/demo_clip.mp4'

/**
 * The dashboard palette.
 *
 * Survivors get their own colour and it is deliberately not red: red already
 * means "hazard" and "critical priority" (CLAUDE.md, dashboard requirements).
 *
 * `survivor` marks survivors and nothing else — bounding boxes, map pins, the
 * dot beside the survivor count. It is never used as a text colour, because a
 * cyan number reads as a category rather than a value and the whole point of
 * the colour is that it means one specific thing.
 *
 * The other four are status colours, ordered by escalation. They apply to
 * priority and hazard state, never to survivors.
 */
export const COLORS = {
  survivor: '#22d3ee', // cyan — survivor marks ONLY, never text
  good: '#4ade80', // status: clear / rescued
  warning: '#fbbf24', // status: medium priority
  serious: '#fb923c', // status: high priority
  critical: '#f87171', // status: hazard, critical priority
}

/** Survivor overlay colours, drawn on the video canvas. */
export const SURVIVOR_COLOR = COLORS.survivor
export const SURVIVOR_LABEL_TEXT = '#04212b'

/**
 * Measured inference throughput on the target device.
 *
 * `null` means exactly that: nobody has run the benchmark yet. The header
 * renders a dash and says "not yet measured" rather than showing a number,
 * because an invented FPS figure on a dashboard a judge is reading is the kind
 * of thing one follow-up question destroys. Set this to the real measurement
 * once `ai/` produces one — the header picks it up with no other change.
 *
 * This lives here rather than coming from the backend because the dashboard
 * has to work with the backend switched off (CLAUDE.md, demo-day constraint 2).
 * It must stay in step with whatever the benchmark records.
 */
export const DEVICE_FPS = null
export const DEVICE_NAME = 'Raspberry Pi 4 Model B'

/**
 * Operating confidence threshold, shown beside the "High Recall" indicator so
 * the claim is backed by the actual number.
 *
 * Mirrors CONFIDENCE_THRESHOLD in `backend/config.py`. If that changes, change
 * this — the frontend cannot read it, since it must render with the backend
 * switched off.
 */
export const CONFIDENCE_THRESHOLD = 0.18

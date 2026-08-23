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
 * Survivor overlay colour.
 *
 * Deliberately not red: red is reserved for hazards and high priority
 * (CLAUDE.md, dashboard requirements). Cyan stays legible over the greys and
 * browns of aerial disaster footage.
 */
export const SURVIVOR_COLOR = '#22d3ee'
export const SURVIVOR_LABEL_TEXT = '#04212b'

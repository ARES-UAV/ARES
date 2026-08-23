/**
 * Tunable constants for the dashboard frontend.
 *
 * Mirrors the intent of `backend/config.py`: anything a judge might ask "where
 * does that number come from?" about lives in one place, not scattered through
 * components.
 *
 * Two kinds of value live here, and the difference matters:
 *
 *   FALLBACK_CONFIG — clip and camera constants that the BACKEND owns. The
 *                     dashboard fetches them from `/api/config` on load and
 *                     renders from that. The copy below is used only when the
 *                     backend cannot be reached, and the header says so.
 *
 *   everything else — genuinely frontend-only: the palette, where the browser
 *                     loads the clip from, the tile server. The backend has no
 *                     opinion on these and never sends them.
 */

/**
 * Clip and camera constants, used ONLY when `/api/config` is unreachable.
 *
 * These must mirror `backend/config.py`. Nothing enforces that — the whole
 * point of the endpoint is that the backend is authoritative when it is up, so
 * a drift here shows up only in the offline path. Keep them in step by hand
 * whenever the backend values change.
 *
 *   clip_fps             Browsers expose no API for a video's true frame rate,
 *                        so it has to be declared rather than measured.
 *                        `demo_clip.mp4` is 23.976 fps (24000/1001, the usual
 *                        NTSC film rate); 24 is close enough that the derived
 *                        frame index does not drift by a whole frame across
 *                        the 27-second clip.
 *
 *   source_width/height  The coordinate space the detection bboxes are
 *                        expressed in, which is NOT necessarily the resolution
 *                        of the video file being played — demo_clip.mp4 is
 *                        actually 1280x676. Boxes are scaled from these
 *                        dimensions to whatever size the video element is
 *                        displayed at; never from videoWidth/videoHeight.
 *
 *   altitude_m,          Fixed per demo clip. There is no live telemetry in
 *   camera_fov_deg,      the prototype, and the pitch discloses that rather
 *   origin_lat/lon       than hiding it. They drive the pixel->GPS conversion,
 *                        so a wrong value here puts every survivor in the
 *                        wrong place on the map.
 */
export const FALLBACK_CONFIG = {
  clip_fps: 24,
  source_width: 1280,
  source_height: 720,
  confidence_threshold: 0.18,
  altitude_m: 20.0,
  camera_fov_deg: 60.0,
  origin_lat: 26.1445,
  origin_lon: 91.7362,
}

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
 * Map tiles.
 *
 * OpenStreetMap needs no API key (CLAUDE.md, demo-day constraint 4). It does
 * need internet, which venue wifi may not provide — the map panel detects
 * failing tiles and says so on screen rather than showing a silent grey void.
 * Before 5 September this should point at a cached tile set or a static
 * georeferenced image; that swap is a change to these two lines and nothing
 * else.
 *
 * The two zoom ceilings are not the same number and the difference matters.
 * OSM renders no tiles past zoom 19, but at 20 m altitude the camera covers
 * only about 23 m of ground — at zoom 19 that entire search area is some 70 px
 * wide and nine survivors land on top of each other. MAX_NATIVE_ZOOM stops
 * Leaflet requesting tiles that do not exist; MAX_ZOOM lets it keep zooming
 * past that by upscaling the last real tile. The base map goes soft, which is
 * the honest signal that it has run out of detail while the survivor positions
 * have not.
 */
export const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
export const TILE_ATTRIBUTION = '&copy; OpenStreetMap contributors'
export const MAP_MAX_NATIVE_ZOOM = 19
export const MAP_MAX_ZOOM = 22
export const MAP_DEFAULT_ZOOM = 20

/**
 * How far the initial auto-fit is allowed to zoom.
 *
 * Lower than MAP_MAX_ZOOM on purpose. Fitting nine survivors who are metres
 * apart into the panel would otherwise zoom past every recognisable feature and
 * open on a blank beige field — technically framed on the survivors, useless
 * for telling anyone where they are. This stops at the last zoom that still
 * shows streets and coastline; the operator can zoom further by hand.
 */
export const MAP_FIT_MAX_ZOOM = 20

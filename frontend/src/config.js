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
 *                        wrong place on the map. origin_lat/lon is where the
 *                        drone sits at FRAME 0, not for the whole clip.
 *
 *   drone_speed_ms,      The assumed flight track. The drone does not hover:
 *   drone_heading_deg    the backend advances the origin along a straight
 *                        constant-velocity line from frame 0, so survivors
 *                        spread along a flight path instead of collapsing
 *                        into the single ~23 m footprint the camera sees at
 *                        one instant. Assumed, not measured — same disclosed
 *                        class as altitude and FOV. Heading is a compass
 *                        bearing: 0 = north, 90 = east, clockwise.
 *
 *                        These two are here for the panel's disclosure text
 *                        only. The conversion itself happens server-side; the
 *                        frontend never recomputes a position from them.
 *
 *   weight_*,            The priority formula's weights, cluster radius and
 *   cluster_radius_m,    band thresholds. The survivor table prints the actual
 *   priority_*_at        formula from these, so a judge reading the screen sees
 *                        the arithmetic that ran rather than a caption someone
 *                        forgot to update. The scoring itself is server-side in
 *                        `backend/priority.py`; the frontend never recomputes a
 *                        score, it only explains one.
 *
 *   hazard_count         How many known hazard positions the backend scored
 *                        against. 0 is the honest current state — hazard
 *                        classification is Phase 2 — and it means the hazard
 *                        term was DROPPED from the average, not scored zero.
 *                        The table says which, because "no hazard nearby" and
 *                        "no hazard detector" are very different claims.
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
  drone_speed_ms: 5.0,
  drone_heading_deg: 45.0,
  weight_confidence: 0.4,
  weight_cluster_size: 0.3,
  weight_hazard_proximity: 0.3,
  cluster_radius_m: 15.0,
  hazard_count: 0,
  priority_serious_at: 0.45,
  priority_critical_at: 0.7,
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
 * The priority ramp: how `Survivor.priority_band` is rendered.
 *
 * Three bands, escalating, taken straight from the status colours above. There
 * is no fourth "clear" band — the backend never emits one, because the
 * lowest-priority person in a disaster zone still needs rescuing and a green
 * row would tell an operator otherwise.
 *
 * Survivor cyan is deliberately absent. Cyan means "this is a survivor" and
 * every row in the table is one, so colouring a row by priority in cyan would
 * say nothing; using it for one band would break its meaning everywhere else.
 *
 * The `label` is not decoration. Colour alone excludes anyone with a colour
 * vision deficiency and anyone reading a projector at the back of a room, so
 * the word is always rendered beside the swatch — never the swatch on its own.
 */
export const PRIORITY_BANDS = {
  warning: { color: COLORS.warning, label: 'Warning' },
  serious: { color: COLORS.serious, label: 'Serious' },
  critical: { color: COLORS.critical, label: 'Critical' },
}

/**
 * Render details for a band string, tolerating one this build does not know.
 *
 * If the backend gains a band the frontend has not been taught, the row shows
 * the raw name in the lowest style rather than rendering a blank cell — an
 * unknown priority must still be visible.
 */
export function priorityBand(band) {
  return PRIORITY_BANDS[band] ?? { color: COLORS.warning, label: band ?? 'Unknown' }
}

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
 * Lower than MAP_MAX_ZOOM on purpose. Fitting a handful of survivors metres
 * apart into the panel would otherwise zoom past every recognisable feature and
 * open on a blank beige field — technically framed on the survivors, useless
 * for telling anyone where they are. This stops at the last zoom that still
 * shows streets and coastline; the operator can zoom further by hand.
 *
 * Re-checked against the moving origin. The assumed flight track spreads the
 * fixture's survivors over roughly 31 m east-west by 18 m north-south, up from
 * 16 x 5 m when the origin was stationary. Leaflet's natural fit for that is
 * still zoom 21, so this cap is still what decides the opening view — but the
 * field now fills a useful fraction of the panel at zoom 20 (~80 m across)
 * rather than sitting in the middle of it. Worth re-running this sum when the
 * fixture is replaced by real footage: a longer clip or a faster track can
 * make the natural fit drop below 20, at which point the cap stops binding
 * and the data frames itself.
 */
export const MAP_FIT_MAX_ZOOM = 20

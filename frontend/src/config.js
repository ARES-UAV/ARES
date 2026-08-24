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
 *                     loads the clip from, where the backend lives. The backend
 *                     has no opinion on these and never sends them.
 */

/**
 * Where the backend is.
 *
 * Lives here rather than in `api.js` because it is not only api.js's any more:
 * the map's tile URL is built from it too, since the tiles are served by the
 * same FastAPI process. One definition, so pointing the dashboard at a
 * different host moves the data and the base map together instead of leaving
 * the map fetching tiles from a server that is no longer there.
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

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
 *   ground_footprint_m   2 * H * tan(FOV/2) — the ground width one frame
 *                        covers. DERIVED, and derived server-side by the same
 *                        `ground_sample_distance` the survivor positions come
 *                        out of, so the figure the mission-parameters panel
 *                        prints is arithmetically the one the map pins were
 *                        placed with. The fallback below is that formula
 *                        evaluated at the fallback altitude and FOV.
 *
 *   device_fps,          Measured inference throughput on the target device,
 *   device_name          and the device it refers to. `null` means exactly
 *                        that: nobody has run the benchmark yet. The
 *                        mission-parameters panel shows a dash and "not yet
 *                        measured" rather than a number — an invented FPS
 *                        figure is the kind of thing one follow-up question
 *                        destroys. It comes from the backend like every other
 *                        constant, so the real measurement lands on screen by
 *                        editing `backend/config.py` and nothing else.
 *
 *   weight_*,            The priority formula's weights, cluster radius and
 *   cluster_radius_m,    the three cuts of the four-band ramp. The survivor
 *   priority_*_at        table prints the actual formula from these, so a
 *                        judge reading the screen sees
 *                        the arithmetic that ran rather than a caption someone
 *                        forgot to update. The scoring itself is server-side in
 *                        `backend/priority.py`; the frontend never recomputes a
 *                        score, it only explains one.
 *
 *   event_sample_        How often the mission event log re-assesses every
 *   interval_s           survivor's priority, in seconds of playback. The log
 *                        panel prints this in its disclosure line, so what a
 *                        judge reads is the cadence that actually ran. It is a
 *                        sampling rate, not smoothing: re-scoring every frame
 *                        floods the log with tracks flickering across a band
 *                        threshold on detector confidence noise. See
 *                        EVENT_SAMPLE_INTERVAL_S in backend/config.py.
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
  ground_footprint_m: 23.094010767585026,
  device_fps: null,
  device_name: 'Raspberry Pi 4 Model B',
  weight_confidence: 0.4,
  weight_cluster_size: 0.3,
  weight_hazard_proximity: 0.3,
  cluster_radius_m: 15.0,
  hazard_count: 0,
  event_sample_interval_s: 1.0,
  priority_medium_at: 0.25,
  priority_high_at: 0.5,
  priority_critical_at: 0.75,
}

/**
 * Where the browser loads the clip from.
 *
 * Served out of `frontend/public/`, not the backend, so the video panel still
 * works with the backend switched off (CLAUDE.md, demo-day constraint 2).
 */
export const CLIP_SRC = '/demo_clip.mp4'

/**
 * The dashboard palette lives in `tokens.css`, not here.
 *
 * Nothing in this file holds a colour value. These are token NAMES, and the
 * rule the whole frontend follows is that a hex literal appears in exactly one
 * file: components reference a role, and the role is defined once. That is not
 * tidiness — the token file's values were measured against a validator for
 * lightness monotonicity, step separation and colour-vision-deficiency
 * distance, and a hex copied into a component is a value that silently stops
 * being the measured one.
 *
 * Two roles matter most and they are deliberately kept apart:
 *
 *   `--survivor`     marks survivor DETECTIONS and nothing else — bounding
 *                    boxes, map pins, the selected row's edge, the playback
 *                    scrubber. Never a text colour and never a priority band:
 *                    a cyan number reads as a category rather than a value,
 *                    and every row in the survivor table is a survivor, so
 *                    colouring priority in cyan would say nothing.
 *
 *   `--priority-*`   the four steps of the ordinal ramp below. One hue,
 *                    monotone light to dark. They mean rank, not status.
 */

/** CSS `var()` reference for a token name, for inline styles. */
export function paint(tokenName) {
  return `var(${tokenName})`
}

/** Survivor overlay colour tokens, resolved for canvas in `theme.js`. */
export { SURVIVOR as SURVIVOR_TOKEN, ON_SURVIVOR as SURVIVOR_LABEL_TOKEN } from './theme.js'

/**
 * The priority ramp: how `Survivor.priority_band` is rendered.
 *
 * An ORDINAL RAMP, not four status colours. The four steps are one hue
 * darkening monotonically, so the ordering survives a projector, a photocopy
 * and a viewer with a colour vision deficiency. The previous version was a
 * green-amber-orange-red rainbow, which failed twice over: a rainbow for
 * ordered data, and a red-green ramp that collapses for roughly 8% of men.
 * See the note at the top of tokens.css for the measurements.
 *
 * `step` is the rank, 1 lowest. It is what the ramp legend and the swatch
 * stack are drawn from, so the visual order comes from the data rather than
 * from the order someone happened to type the keys in.
 *
 * The `label` is not decoration. Colour alone excludes anyone with a colour
 * vision deficiency and anyone reading a projector from the back of a room, so
 * the word is ALWAYS rendered beside the swatch — never the swatch on its own.
 *
 * There is no "clear" band. `low` is the bottom of the ramp, drawn in a pale
 * alarm colour rather than a green, because the lowest-priority person in a
 * disaster zone still needs rescuing.
 */
export const PRIORITY_BANDS = {
  low: { step: 1, token: '--priority-low', label: 'Low' },
  medium: { step: 2, token: '--priority-medium', label: 'Medium' },
  high: { step: 3, token: '--priority-high', label: 'High' },
  critical: { step: 4, token: '--priority-critical', label: 'Critical' },
}

/** The ramp in rank order, lowest first. Legends read this, never the object. */
export const PRIORITY_RAMP = Object.entries(PRIORITY_BANDS)
  .map(([name, band]) => ({ name, ...band }))
  .sort((a, b) => a.step - b.step)

/**
 * Band names this frontend understands but the backend no longer emits.
 *
 * The ramp used to be three status bands. If an older `backend/priority.py`
 * is running — Robin's version of that module is still to land, and it may be
 * branched from before the rename — the dashboard renders the right step
 * instead of falling through to "Unknown". Cheap insurance against a mismatch
 * discovered on stage.
 */
const LEGACY_BANDS = {
  warning: 'medium',
  serious: 'high',
}

/**
 * Render details for a band string, tolerating one this build does not know.
 *
 * An unrecognised band shows its raw name at the TOP of the ramp, not the
 * bottom. Getting this wrong in the safe-looking direction would quietly rank
 * someone last because a string did not match; erring upward is the failure a
 * search-and-rescue dashboard should have.
 */
export function priorityBand(band) {
  const key = PRIORITY_BANDS[band] ? band : LEGACY_BANDS[band]
  const known = PRIORITY_BANDS[key]
  if (known) return { ...known, name: key, color: paint(known.token) }
  return {
    step: PRIORITY_BANDS.critical.step,
    token: PRIORITY_BANDS.critical.token,
    color: paint(PRIORITY_BANDS.critical.token),
    label: band ?? 'Unknown',
    name: band ?? 'unknown',
  }
}

/**
 * Map tiles — served by the backend from disk, not fetched from the internet.
 *
 * Demo-day constraint 3 in CLAUDE.md: tiles need internet and venue wifi
 * fails. `tools/fetch_tiles.py` downloads the OpenStreetMap tiles covering the
 * demo area into `backend/data/tiles/`, and `GET /tiles/{z}/{x}/{y}.png`
 * serves them. Nothing on the map's path leaves the machine on demo day.
 *
 * Still OpenStreetMap, so still no API key (constraint 4), and still OSM's
 * data — the attribution stays and says the tiles are a local cache.
 *
 * The banner in MapPanel does not go away, it changes meaning: it used to
 * report a dead network, and now reports a view outside the bundled box. Both
 * are the same fact on screen — pins are still plotted, the base map is not —
 * so the panel needs no change. Zooming or panning far enough gets 404s from
 * the backend and the banner appears, which is the honest signal that the
 * cache has run out rather than that the map is broken.
 *
 * One thing this trades away: with the backend switched off there are now no
 * tiles at all, where before an internet connection would have supplied them.
 * That is the demo-day shape on purpose — the venue is likelier to lose wifi
 * than the laptop is to lose its own uvicorn — but constraint 2's
 * backend-off path is a pin-only map, and the banner is what says so.
 *
 * The two zoom ceilings are not the same number and the difference matters.
 * OSM renders no tiles past zoom 19, so nothing past 19 was ever fetched;
 * meanwhile at 20 m altitude the camera covers only about 23 m of ground, so
 * at zoom 19 that entire search area is some 70 px wide and nine survivors
 * land on top of each other. MAX_NATIVE_ZOOM stops Leaflet requesting tiles
 * that do not exist; MAX_ZOOM lets it keep zooming past that by upscaling the
 * last real tile. The base map goes soft, which is the honest signal that it
 * has run out of detail while the survivor positions have not.
 */
export const TILE_URL = `${API_BASE}/tiles/{z}/{x}/{y}.png`
export const TILE_ATTRIBUTION =
  '&copy; OpenStreetMap contributors &middot; tiles cached locally'
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

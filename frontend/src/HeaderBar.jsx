import { COLORS, DEVICE_FPS, DEVICE_NAME } from './config.js'

/**
 * The dashboard's top status bar.
 *
 * Every figure here is derived from the same playback state App holds, so they
 * cannot drift out of step with the video, the map or the survivor table. This
 * component computes nothing — it is handed the numbers.
 *
 * `tabular-nums` is on every figure. Without it the proportional digits shift
 * width as the count changes and the whole bar twitches while the clip plays,
 * which reads as instability in a dashboard whose job is to look trustworthy.
 */

/** One cell of the bar. `mark` is an optional colour swatch beside the label. */
function Stat({ label, sublabel, mark, children }) {
  return (
    <div className="flex-1 px-5 py-3 min-w-[11rem]">
      <div className="flex items-center gap-1.5">
        {mark && (
          <span
            aria-hidden="true"
            className="h-2 w-2 shrink-0 rounded-sm"
            style={{ backgroundColor: mark }}
          />
        )}
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          {label}
        </span>
      </div>

      <div className="mt-1">{children}</div>

      <div className="mt-0.5 text-[11px] tabular-nums text-slate-500">{sublabel}</div>
    </div>
  )
}

/** A large figure. Slate, never a status colour — the colours carry meaning. */
function Figure({ children, muted = false }) {
  return (
    <span
      className={`text-3xl font-semibold leading-none tabular-nums ${
        muted ? 'text-slate-600' : 'text-slate-100'
      }`}
    >
      {children}
    </span>
  )
}

/** A small caps pill, tinted by a palette colour. */
function Pill({ color, children }) {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
      style={{ color, backgroundColor: `${color}1f` }}
    >
      {children}
    </span>
  )
}

/**
 * @param {object}  props
 * @param {object}  props.config              clip constants in force right now
 * @param {boolean} props.configOffline       true when `config` is the local fallback
 * @param {number}  props.frameDetectionCount raw records for the current frame
 * @param {number}  props.survivorsSoFar      distinct track_ids up to this frame
 * @param {number}  props.survivorsInClip     distinct track_ids in the whole clip
 * @param {object=} props.selectedSurvivor    the survivor selected on the map
 * @param {number|null} props.selectedTrackId
 * @param {function} props.onClearSelection
 */
export default function HeaderBar({
  config,
  configOffline,
  frameDetectionCount,
  survivorsSoFar,
  survivorsInClip,
  selectedSurvivor,
  selectedTrackId,
  onClearSelection,
}) {
  const fpsMeasured = DEVICE_FPS !== null

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
      <div className="flex flex-wrap items-stretch divide-x divide-slate-800">
        <div className="flex items-center gap-3 px-5 py-3">
          <span className="text-lg font-semibold tracking-tight text-slate-100">ARES</span>
          <div className="hidden sm:block">
            <span className="block text-[11px] leading-tight text-slate-500">
              Adaptive Rescue
              <br />
              and Exploration System
            </span>
            {/* The dashboard renders whether or not the backend is up
                (CLAUDE.md, demo-day constraint 2). When it is down the clip and
                camera constants below come from the frontend's own copy, and
                saying so is the difference between a resilient dashboard and
                one quietly showing stale numbers. */}
            {configOffline && (
              <span className="mt-1 inline-block">
                <Pill color={COLORS.warning}>offline · local constants</Pill>
              </span>
            )}
          </div>
        </div>

        {/* Two counts, deliberately worded so they cannot be read as the same
            thing: one is per-frame and raw, the other is cumulative and
            de-duplicated. The first mockup's worst flaw was a header count that
            disagreed with the table below it. */}
        <Stat
          label="Raw detections"
          sublabel="this frame · before de-duplication"
        >
          <Figure>{frameDetectionCount}</Figure>
        </Stat>

        <Stat
          label="Survivors tracked"
          sublabel={`unique IDs so far · ${survivorsInClip} in full clip`}
          mark={COLORS.survivor}
        >
          <Figure>{survivorsSoFar}</Figure>
        </Stat>

        {/* Mirrors the map selection. Clicking a pin has to land somewhere the
            eye already is, or the only feedback is a highlight on a video the
            viewer may not be looking at. */}
        <Stat
          label="Selected survivor"
          sublabel={
            selectedSurvivor
              ? `${selectedSurvivor.latitude.toFixed(5)}, ${selectedSurvivor.longitude.toFixed(5)}`
              : 'click a marker on the map'
          }
          mark={selectedTrackId !== null ? COLORS.survivor : undefined}
        >
          <div className="flex items-center gap-2">
            <Figure muted={selectedTrackId === null}>
              {selectedTrackId !== null ? `#${selectedTrackId}` : '—'}
            </Figure>
            {selectedTrackId !== null && (
              <button
                type="button"
                onClick={onClearSelection}
                className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400 hover:border-slate-500 hover:text-slate-200"
              >
                clear
              </button>
            )}
          </div>
        </Stat>

        {/* Honest by construction: no benchmark has been run, so no number is
            shown. See DEVICE_FPS in config.js. */}
        <Stat
          label="On-device FPS"
          sublabel={DEVICE_NAME}
        >
          <div className="flex items-center gap-2">
            <Figure muted={!fpsMeasured}>{fpsMeasured ? DEVICE_FPS.toFixed(1) : '—'}</Figure>
            {!fpsMeasured && <Pill color={COLORS.warning}>not yet measured</Pill>}
          </div>
        </Stat>

        <Stat
          label="Detection mode"
          sublabel={`confidence ≥ ${config.confidence_threshold.toFixed(2)} · recall over precision`}
        >
          <span className="text-xl font-semibold leading-none text-slate-100">
            High Recall
          </span>
        </Stat>
      </div>
    </header>
  )
}

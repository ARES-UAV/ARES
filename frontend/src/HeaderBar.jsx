/**
 * The dashboard's top status bar.
 *
 * Every figure here is derived from the same playback state App holds, so they
 * cannot drift out of step with the video, the map or the survivor table. This
 * component computes nothing — it is handed the numbers.
 *
 * Two rows, and the split is a layout decision made for 1280px, which is
 * projector resolution and the only width that actually has to work. Six stat
 * cells in one strip needed about 1250px before they wrapped into a ragged
 * second line; an identity row above three wide stat cells holds at 1280 with
 * room to spare and puts the numbers that change during playback on their own
 * baseline, where the eye can find them from the back of a room.
 *
 * It is also kept THIN, because it is row one of four and the other three have
 * to fit under it at 1280×720 without scrolling. App measures this bar and
 * hands the rest of the viewport to the operational panels, so a loose line of
 * padding here is a row the survivor queue does not get.
 *
 * Every figure carries `.figure` from tokens.css, which is what puts
 * `--font-data` and `tabular-nums` on it. Without that the proportional digits
 * shift width as counts change and the whole bar twitches while the clip
 * plays, which reads as instability in a dashboard whose job is to look
 * trustworthy.
 */

/** Small caps label above a value. */
function Label({ mark, children }) {
  return (
    <div className="flex items-center gap-1.5">
      {mark && (
        <span
          aria-hidden="true"
          className="h-2 w-2 shrink-0 rounded-sm bg-survivor"
        />
      )}
      <span className="eyebrow">{children}</span>
    </div>
  )
}

/**
 * One cell of the stat strip.
 *
 * Padding and internal margins are deliberately tight. This bar is row one of a
 * layout whose other three rows have to fit in the same 720px, and every pixel
 * it takes comes straight out of the survivor queue's row count. The figure
 * itself is NOT shrunk to pay for that — it is the number someone reads from
 * the back of a room, and 34px is what makes that work.
 */
function Stat({ label, sublabel, mark, children }) {
  return (
    <div className="flex-1 border-l border-edge-soft px-4 py-2 first:border-l-0">
      <Label mark={mark}>{label}</Label>
      <div className="mt-1">{children}</div>
      <div className="figure mt-0.5 text-eyebrow text-ink-muted">{sublabel}</div>
    </div>
  )
}

/**
 * A large figure. Ink, never a ramp colour — the priority ramp means rank and
 * survivor cyan means "this is a detection", and a count is neither.
 */
function Figure({ children, muted = false }) {
  return (
    <span
      className={`figure text-figure leading-none font-semibold ${
        muted ? 'text-ink-muted' : 'text-ink'
      }`}
    >
      {children}
    </span>
  )
}

/**
 * A small caps pill for a caveat.
 *
 * Deliberately drawn in the "not measured" tokens rather than a ramp step. A
 * pill saying "not yet measured" in an alarm colour would read as a priority
 * reading; the token file's answer to an unmeasured value is that it should
 * look absent, not like a state.
 */
function Caveat({ children }) {
  return (
    <span className="inline-flex items-center rounded bg-unmeasured-bg px-1.5 py-0.5 text-eyebrow font-semibold tracking-wide text-unmeasured-ink uppercase">
      {children}
    </span>
  )
}

/**
 * Today, as the mission date.
 *
 * Computed rather than written down. A placeholder date is stale the day after
 * someone types it and reads as an unfinished dashboard (CLAUDE.md's design
 * review says exactly this), and there is no date this could be other than the
 * day it is being run.
 */
function missionDate() {
  return new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/**
 * @param {object}  props
 * @param {object}  props.config              clip constants in force right now
 * @param {boolean} props.configOffline       true when `config` is the local fallback
 * @param {number}  props.frameDetectionCount raw records for the current frame
 * @param {number|null} props.survivorsSoFar  survivors found by this frame — the
 *                                            length of the exact array the
 *                                            survivor table renders as rows.
 *                                            null while the list is unavailable.
 * @param {number|null} props.survivorsInClip survivors in the whole clip
 * @param {object=} props.selectedSurvivor    the survivor selected on the map
 * @param {number|null} props.selectedTrackId
 * @param {function} props.onClearSelection
 * @param {function=} props.ref             App's callback ref. It measures this
 *                                          bar and gives the operational block
 *                                          exactly the rest of the viewport, so
 *                                          the four live panels sit above the
 *                                          fold. React 19 passes `ref` as an
 *                                          ordinary prop; no forwardRef needed.
 */
export default function HeaderBar({
  ref,
  config,
  configOffline,
  frameDetectionCount,
  survivorsSoFar,
  survivorsInClip,
  selectedSurvivor,
  selectedTrackId,
  onClearSelection,
}) {
  return (
    <header ref={ref} className="sticky top-0 z-50 border-b border-edge bg-surface-1">
      {/* ── Identity row ──────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-edge-soft px-4 py-2">
        <div className="flex items-baseline gap-2.5">
          <span className="text-title leading-none font-bold tracking-tight text-ink">
            ARES
          </span>
          <span className="hidden text-fine text-ink-muted sm:inline">
            Adaptive Rescue and Exploration System
          </span>
        </div>

        <div className="flex items-baseline gap-2">
          <span className="eyebrow">Mission date</span>
          <span className="figure text-fine text-ink-soft">{missionDate()}</span>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-x-6 gap-y-2">
          {/* Required on screen (CLAUDE.md, dashboard requirements). The
              threshold is the reason for the mode, so it is printed next to
              it rather than left as a claim. */}
          <div className="flex items-baseline gap-2">
            <span className="eyebrow">Detection mode</span>
            <span className="text-fine font-semibold text-ink">High Recall</span>
            <span className="figure text-eyebrow text-ink-muted">
              confidence {config.confidence_threshold.toFixed(2)} and above
            </span>
          </div>

          {/* On-device FPS is NOT here. It lives in the mission-parameters
              panel with a provenance tag beside it, because the honest form of
              that figure is "not yet measured" and a bare dash in the header
              cannot carry that. Duplicating it would also mean two "not
              measured" pills on one screen saying the same thing. */}

          {/* The dashboard renders whether or not the backend is up
              (CLAUDE.md, demo-day constraint 2). When it is down the clip and
              camera constants come from the frontend's own copy, and saying so
              is the difference between a resilient dashboard and one quietly
              showing stale numbers. */}
          {configOffline && <Caveat>offline · local constants</Caveat>}
        </div>
      </div>

      {/* ── Stat strip ────────────────────────────────────────────── */}
      <div className="flex flex-wrap">
        {/* Two counts, deliberately worded so they cannot be read as the same
            thing: one is per-frame and raw, the other is cumulative and
            de-duplicated. The first mockup's worst flaw was a header count
            that disagreed with the table below it. */}
        <Stat label="Raw detections" sublabel="this frame · before de-duplication">
          <Figure>{frameDetectionCount}</Figure>
        </Stat>

        {/* This figure is `survivorsFound.length` — the length of the very
            array the survivor table below renders as rows. Not a second tally
            of track IDs that happens to agree with it: the table's row count
            and this number are the same value, which is the only version of
            "counts reconcile" that survives someone editing one of them.

            null means the survivor list has not arrived (or failed), which is
            not the same claim as zero survivors — so it shows a dash. */}
        <Stat
          label="Survivors tracked"
          sublabel={
            survivorsSoFar === null
              ? 'survivor list unavailable'
              : `unique IDs so far · ${survivorsInClip} in full clip`
          }
          mark
        >
          <Figure muted={survivorsSoFar === null}>
            {survivorsSoFar === null ? '—' : survivorsSoFar}
          </Figure>
        </Stat>

        {/* Mirrors the selection, wherever it was made. Clicking a pin or a
            table row has to land somewhere the eye already is, or the only
            feedback is a highlight on a panel the viewer may not be looking
            at. */}
        <Stat
          label="Selected survivor"
          sublabel={
            selectedSurvivor
              ? `${selectedSurvivor.latitude.toFixed(5)}, ${selectedSurvivor.longitude.toFixed(5)}`
              : 'click a map marker or a table row'
          }
          mark={selectedTrackId !== null}
        >
          <div className="flex items-center gap-2">
            <Figure muted={selectedTrackId === null}>
              {selectedTrackId !== null ? `#${selectedTrackId}` : '—'}
            </Figure>
            {selectedTrackId !== null && (
              <button
                type="button"
                onClick={onClearSelection}
                className="rounded border border-edge px-1.5 py-0.5 text-eyebrow font-semibold tracking-wide text-ink-soft uppercase hover:border-ink-muted hover:text-ink"
              >
                clear
              </button>
            )}
          </div>
        </Stat>
      </div>
    </header>
  )
}

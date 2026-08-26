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
 * second line; an identity row above four stat cells holds at 1280 with room
 * to spare and puts the numbers that change during playback on their own
 * baseline, where the eye can find them from the back of a room. The
 * sublabels are written to fit ~43 monospace characters, which is what a
 * quarter of 1280px leaves once the cell padding is taken out.
 *
 * ── The three counts, and why there are three ───────────────────────
 * Raw detections, track IDs issued, confirmed survivors. The last two are
 * different numbers on purpose and the labels have to make that read as
 * deliberate, because the gap between them is large: on the current clip the
 * tracker issues 333 IDs and 23 of them clear the persistence threshold.
 *
 * That gap is the price of `confidence_threshold` being 0.18. A recall-first
 * detector reports anything person-shaped, the tracker dutifully gives each
 * one an identity, and most of those identities last a fraction of a second.
 * Showing only the ID count would overstate the survivors by an order of
 * magnitude; showing only the confirmed count would hide what the filter is
 * doing and leave a judge no way to check it. So both are on screen, next to
 * each other, and the identity row above states the rule that separates them.
 *
 * All three descend from one array of detection records — see App, where they
 * are derived. This component computes nothing; it is handed the numbers.
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

import { FALLBACK_CONFIG } from './config.js'

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
 * A persistence threshold in seconds, at the precision it is configured with.
 *
 * `2.5` prints as "2.5" and `3` prints as "3", rather than a fixed two
 * decimals turning a round rule into "3.00 s" — a number that looks measured
 * when it is a chosen constant.
 */
/**
 * The persistence rule in the unit it is APPLIED in.
 *
 * `seconds()` below states the rule; this states what the rule costs a track.
 * They are not interchangeable, and the header uses this one: confirmation
 * counts DISTINCT FRAMES a track was detected in, not elapsed time. A track
 * detected in half the frames it is alive for exists for twice the duration
 * before it confirms — on this clip, track 1409 ran 125 frames and confirmed
 * on its 60th sighting. "Tracked for 2.5 s" would be a claim the code does not
 * make; "seen in 60 frames" is exactly what it does.
 */
function trackedFrames(config) {
  return config.min_track_frames ?? FALLBACK_CONFIG.min_track_frames
}

/**
 * The measured on-device throughput, or null when nobody has run a benchmark.
 *
 * Kept as a helper rather than read inline so the null case is expressed once.
 * `null` is a real state, not a missing value: it means the honest answer is
 * "not yet measured", and the header renders nothing at all rather than a dash
 * that reads like a broken number.
 */
function deviceThroughput(config) {
  return config.device_fps ?? FALLBACK_CONFIG.device_fps ?? null
}

function deviceLabel(config) {
  return config.device_name ?? FALLBACK_CONFIG.device_name
}

function seconds(value) {
  // `??` for a backend running from before this field existed — the same
  // tolerance MissionParameters applies to `ground_footprint_m`. The bundled
  // constant is the honest stand-in: it is what the rule is meant to be, and
  // the offline badge already says when local constants are in force.
  const s = value ?? FALLBACK_CONFIG.min_track_seconds
  return String(Number(s.toFixed(2)))
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
 * @param {number}  props.uniqueTracksSoFar  distinct track IDs issued by this
 *                                           frame — pre-filter tracker output
 * @param {number}  props.uniqueTracksInClip distinct track IDs in the whole clip
 * @param {number|null} props.survivorsSoFar  survivors CONFIRMED by this frame —
 *                                            the length of the exact array the
 *                                            survivor table renders as rows.
 *                                            null while the list is unavailable.
 * @param {number|null} props.survivorsInClip confirmed survivors in the whole clip
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
  uniqueTracksSoFar,
  uniqueTracksInClip,
  survivorsSoFar,
  survivorsInClip,
  selectedSurvivor,
  selectedTrackId,
  onClearSelection,
}) {
  const deviceFps = deviceThroughput(config)
  const deviceName = deviceLabel(config)

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
              it rather than left as a claim — and the persistence rule is
              printed next to the threshold for the same reason. They are two
              halves of one decision: the low threshold is what lets the
              detector report anything person-shaped, and the persistence rule
              is what stops those reports being counted as people. Reading
              them together is what makes the two survivor figures below
              legible as a deliberate pair rather than a discrepancy. */}
          <div className="flex items-baseline gap-2">
            <span className="eyebrow">Detection mode</span>
            <span className="text-fine font-semibold text-ink">High Recall</span>
            <span className="figure text-eyebrow text-ink-muted">
              confidence {config.confidence_threshold.toFixed(2)} and above ·
              confirmed on {trackedFrames(config)} frames of sightings
            </span>
          </div>

          {/* On-device FPS lives here now. It did not used to: while the
              figure was `None`, the honest form of it was "not yet measured",
              and a bare dash in a header cannot carry that qualification — so
              it stayed in the mission-parameters panel where a provenance tag
              could sit beside it.

              It is measured now (Qualcomm AI Hub, real silicon), and CLAUDE.md
              requires the measured figure on screen. The full provenance —
              which board, INT8, the 100% NPU placement, and the fact that INT8
              accuracy is a separate unmeasured thing — still lives in the
              parameters panel. This is the number; that is the footnote.

              Rendered only when it exists, so the `None` path still degrades
              to the old behaviour rather than printing a dash. */}
          {deviceFps !== null && (
            <div className="flex items-baseline gap-2">
              <span className="eyebrow">On-device</span>
              <span className="figure text-fine font-semibold text-ink">
                {deviceFps.toFixed(1)} fps
              </span>
              <span className="figure text-eyebrow text-ink-muted">
                {deviceName} · int8 · measured
              </span>
            </div>
          )}

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
        {/* Three counts, deliberately worded so no two can be read as the same
            thing: one is per-frame and raw, one is cumulative and
            de-duplicated, one is cumulative and filtered. The first mockup's
            worst flaw was a header count that disagreed with the table below
            it, and the fix is not fewer numbers — it is numbers that say what
            they are counting. */}
        <Stat label="Raw detections" sublabel="this frame · pre de-duplication">
          <Figure>{frameDetectionCount}</Figure>
        </Stat>

        {/* The tracker's raw output: how many identities it has issued, before
            anything is thrown away. This is NOT a survivor count and is not
            labelled as one — flicker and ID switches are in it, which is
            precisely why it is worth showing. It is what the number would be
            without the filter, standing next to what it is with one.

            Read off the same detection index the raw figure above comes from,
            so both are the one `detections` array counted two ways rather than
            two datasets. */}
        <Stat
          label="Track IDs issued"
          sublabel={`so far · ${uniqueTracksInClip} in full clip`}
        >
          <Figure>{uniqueTracksSoFar}</Figure>
        </Stat>

        {/* This figure is `survivorsFound.length` — the length of the very
            array the survivor table below renders as rows. Not a second tally
            of track IDs that happens to agree with it: the table's row count
            and this number are the same value, which is the only version of
            "counts reconcile" that survives someone editing one of them.

            It sits directly right of the ID count so the two are read as a
            pair. The sublabel carries the rule in the unit the rule is written
            in — a duration — with the frame count it works out to at this
            clip's rate beside it, because the same 2.5 s is 60 frames here and
            3 on the Pi.

            null means the survivor list has not arrived (or failed), which is
            not the same claim as zero survivors — so it shows a dash. */}
        <Stat
          label="Confirmed survivors"
          sublabel={
            survivorsSoFar === null
              ? 'survivor list unavailable'
              : `seen in ≥${trackedFrames(config)} frames · ${survivorsInClip} in full clip`
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

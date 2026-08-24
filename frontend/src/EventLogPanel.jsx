import { useEffect, useMemo, useRef, useState } from 'react'
import { frameTimecode } from './clock.js'
import { FALLBACK_CONFIG, paint, priorityBand } from './config.js'
import { buildMissionLog, entriesThrough } from './missionLog.js'

/**
 * The mission event log — what happened, when, against the playback clock.
 *
 * Styled as a terminal because that is what it is: a monospace, append-only
 * transcript with the newest line at the bottom. The type is `--font-data`
 * throughout, which is what keeps the timestamp and tag columns in a straight
 * edge — a proportional font turns a log into ragged prose.
 *
 * ── Every line is derived ────────────────────────────────────────────
 * Cluster and priority lines come from `/api/events`, where they are computed
 * by the same `backend.localize` and `backend.priority` the map pins and the
 * survivor table come out of. Confirmation lines are the survivor roster
 * itself, one per element of the array whose length is the header's confirmed
 * survivor count, placed at the frame each track cleared the persistence
 * threshold. Nothing is authored — see `missionLog.js` and CLAUDE.md's demo
 * footage policy.
 *
 * A track the tracker issued an ID for but which never lasted
 * `min_track_seconds` gets no line at all, and that is the log agreeing with
 * the header: the ID count above is what the tracker emitted, this log is what
 * the dashboard is willing to call a person, and the closing summary prints
 * both so the difference is on screen rather than inferred.
 *
 * ── Colour ───────────────────────────────────────────────────────────
 * Each line carries a left gutter stripe, and the stripe is the only place
 * colour appears as an accent:
 *
 *   survivor cyan   detection events — a survivor confirmed, a cluster
 *                   formed.
 *   the priority    band events, in the band being reported.
 *     ramp
 *   muted ink       system lines: replay start, end of clip.
 *
 * The stripe is a stripe and not coloured text on purpose. tokens.css states
 * the rule — survivor cyan is never a text colour — and the same pattern is
 * already how the survivor table marks a selected row. Band names are
 * rendered the way `PriorityCell` renders them, as a swatch beside the word,
 * because the ramp is ordinal: it tells you "darker than that one", never
 * which band this is, so the word is never dropped.
 *
 * ── Scrubbing ────────────────────────────────────────────────────────
 * The visible set is every entry at or before `currentFrame`. Drag the
 * scrubber backwards and the later lines are gone, because they have not
 * happened at the instant on screen. A log that kept them would be describing
 * a frame the operator is no longer looking at.
 */

/** How close to the bottom still counts as "following the clock", in px. */
const PIN_THRESHOLD_PX = 24

/** The tag column, in characters. Wide enough for the longest tag below. */
const TAG = {
  replay_start: 'REPLAY',
  survivor_confirmed: 'CONFIRM',
  cluster_formed: 'CLUSTER',
  priority_assessed: 'ASSESS',
  priority_changed: 'PRIORITY',
  clip_end: 'END',
}

/**
 * A score, at a precision that cannot contradict the band beside it.
 *
 * THREE decimals, where the survivor table uses two, and the difference is
 * load-bearing rather than an inconsistency. The band cuts are 0.25 / 0.50 /
 * 0.75, so a score of 0.7499 rounds to "0.75" at two decimals and the line
 * then reads "lowered to High at 0.75" directly under a table stating that
 * critical begins at 0.75. The number would be right, the band would be right,
 * and the pair would look like a bug to the one person most likely to check.
 *
 * The table can round to two because it never prints a band boundary next to
 * the score; a log line reporting a THRESHOLD CROSSING always does.
 */
function score(value) {
  return value.toFixed(3)
}

/** A band as the survivor table renders it: swatch, then the word. */
function Band({ band }) {
  const resolved = priorityBand(band)
  return (
    <span className="inline-flex items-center gap-1.5 align-baseline">
      <span
        aria-hidden="true"
        className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
        style={{ backgroundColor: resolved.color }}
      />
      <span className="font-semibold text-ink">{resolved.label}</span>
    </span>
  )
}

/** The accent for a line's gutter stripe. */
function stripeToken(entry) {
  switch (entry.kind) {
    case 'survivor_confirmed':
    case 'cluster_formed':
      return '--survivor'
    case 'priority_assessed':
    case 'priority_changed':
      return priorityBand(entry.toBand).token
    default:
      return '--ink-muted'
  }
}

/**
 * One line's message.
 *
 * The system lines are handed the dashboard's shared figures rather than
 * carrying their own: the closing summary prints `survivorsInClip`,
 * `uniqueTracksInClip` and `totalDetections`, which are the header's three
 * numbers. A summary that counted the log's own lines would be a fourth tally
 * of the same people.
 */
function Message({
  entry,
  fps,
  lastFrame,
  minTrackFrames,
  survivorsInClip,
  uniqueTracksInClip,
  totalDetections,
}) {
  switch (entry.kind) {
    case 'replay_start':
      return (
        <>
          <span className="text-ink">Replay started</span>
          <span className="text-ink-muted">
            {' '}
            — {frameTimecode(lastFrame, fps)} of stored detections at {fps} fps
            declared, {lastFrame + 1} frames. No live inference.
          </span>
        </>
      )

    case 'survivor_confirmed':
      // First sighting, then the frame count, then the confidence at this
      // instant. The frame count is doing real work and is not decoration:
      // the rule is "appeared in N frames", NOT "was tracked continuously for
      // N frames", and a track that drops out and returns takes longer than
      // the threshold in wall-clock time to accumulate them. Without the
      // count, a line confirming at 00:05.8 a track first seen at 00:02.0
      // reads as a 3.8 s threshold contradicting the 2.5 s in the header. The
      // count is the reconciliation, and it is always exactly the threshold —
      // that is what confirmation means.
      return (
        <>
          <span className="text-ink">Survivor confirmed</span>
          <span className="text-ink-soft"> #{entry.trackId}</span>
          <span className="text-ink-muted">
            {' '}
            — first seen {frameTimecode(entry.firstFrame, fps)},{' '}
            {minTrackFrames} frames tracked
            {entry.confidence != null && `, confidence ${entry.confidence.toFixed(2)}`}
          </span>
        </>
      )

    case 'cluster_formed':
      return (
        <>
          <span className="text-ink">Cluster</span>
          <span className="text-ink-soft">
            {' '}
            {entry.trackIds.map((id) => `#${id}`).join(' ')}
          </span>
          <span className="text-ink-muted">
            {' '}
            — {entry.trackIds.length} within cluster radius
          </span>
        </>
      )

    case 'priority_assessed':
      return (
        <>
          <span className="text-ink-soft">#{entry.trackId}</span>
          <span className="text-ink-muted"> assessed </span>
          <Band band={entry.toBand} />
          <span className="text-ink-muted"> at {score(entry.score)}</span>
        </>
      )

    case 'priority_changed': {
      const rising = priorityBand(entry.toBand).step > priorityBand(entry.fromBand).step
      return (
        <>
          <span className="text-ink-soft">#{entry.trackId}</span>
          <span className="text-ink-muted"> {rising ? 'escalated' : 'lowered'} </span>
          <Band band={entry.fromBand} />
          <span className="text-ink-muted"> → </span>
          <Band band={entry.toBand} />
          <span className="text-ink-muted"> at {score(entry.score)}</span>
        </>
      )
    }

    case 'clip_end':
      // The header's three figures, in one sentence and in the same order, so
      // the closing line is a restatement of the bar at the top rather than a
      // fourth count of the same clip.
      return (
        <>
          <span className="text-ink">End of clip</span>
          <span className="text-ink-muted">
            {' '}
            — {survivorsInClip ?? '—'} survivors confirmed from{' '}
            {uniqueTracksInClip} track IDs and {totalDetections} raw detections
          </span>
        </>
      )

    default:
      return null
  }
}

export default function EventLogPanel({
  events,
  eventsError,
  survivors,
  index,
  config,
  currentFrame,
  lastFrame,
  survivorsInClip,
  uniqueTracksInClip,
}) {
  const scrollRef = useRef(null)

  // Whether the log is following the clock. It stops following the moment the
  // operator scrolls up to read something and starts again when they scroll
  // back to the bottom — a log that yanks itself down mid-read is unusable in
  // exactly the moment someone is trying to check a line.
  const [pinned, setPinned] = useState(true)

  const fps = config.clip_fps

  // What "confirmed" cost this track, in the unit the log is keyed on. `??`
  // for a backend predating the field, as elsewhere.
  const minTrackFrames =
    config.min_track_frames ??
    Math.trunc(
      (config.min_track_seconds ?? FALLBACK_CONFIG.min_track_seconds) * fps,
    )

  // The whole clip, built once. Which lines are VISIBLE is a per-frame
  // comparison below; rebuilding the list 24 times a second to change that
  // would be the same work over and over.
  const entries = useMemo(
    () => buildMissionLog({ events, survivors, index, lastFrame }),
    [events, survivors, index, lastFrame],
  )

  const visible = useMemo(
    () => entriesThrough(entries, currentFrame),
    [entries, currentFrame],
  )

  useEffect(() => {
    const element = scrollRef.current
    if (!element || !pinned) return
    element.scrollTop = element.scrollHeight
  }, [visible.length, pinned])

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex shrink-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="eyebrow">Mission event log</h2>
        <span className="figure text-eyebrow text-ink-muted">
          every line derived from detections · none authored
        </span>
      </div>

      <div
        ref={scrollRef}
        onScroll={(event) => {
          const { scrollTop, scrollHeight, clientHeight } = event.currentTarget
          setPinned(scrollHeight - scrollTop - clientHeight <= PIN_THRESHOLD_PX)
        }}
        // A log region, not a live region: it can append a dozen lines in a
        // second and a screen reader announcing all of them would drown the
        // rest of the dashboard. It is focusable so it can be scrolled by
        // keyboard, which a scrolling box otherwise cannot be.
        role="log"
        tabIndex={0}
        aria-label="Mission event log"
        className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-edge bg-surface-0 py-1.5"
        style={{ fontFamily: 'var(--font-data)' }}
      >
        {eventsError && (
          // The log still runs — confirmations and the summary come from the
          // roster, not from this endpoint. Saying which half is missing beats
          // a shorter log that looks complete.
          <div
            className="mb-1 flex gap-3 px-3 py-1 text-fine"
            style={{ boxShadow: `inset 3px 0 0 0 ${paint('--hazard')}` }}
          >
            <span className="shrink-0 text-ink-muted">--:--.-</span>
            <span className="w-20 shrink-0 text-ink-muted">TIMELINE</span>
            <span className="text-ink-soft">
              Cluster and priority events unavailable — {eventsError}. Survivor
              confirmations below still play.
            </span>
          </div>
        )}

        {visible.length === 0 && !eventsError && (
          <p className="px-3 py-1 text-fine text-ink-muted">
            Waiting for the playback clock…
          </p>
        )}

        {visible.map((entry) => (
          <div
            key={entry.id}
            className="flex gap-3 px-3 py-1 text-fine leading-relaxed"
            style={{ boxShadow: `inset 3px 0 0 0 ${paint(stripeToken(entry))}` }}
          >
            {/* Clip time, never wall-clock time. The frame index is the
                dashboard's real key and this is its human reading. */}
            <span className="shrink-0 tabular-nums text-ink-muted">
              {frameTimecode(entry.frame, fps)}
            </span>
            <span className="w-20 shrink-0 text-eyebrow font-semibold tracking-wider text-ink-muted uppercase">
              {TAG[entry.kind]}
            </span>
            <span className="min-w-0">
              <Message
                entry={entry}
                fps={fps}
                lastFrame={lastFrame}
                minTrackFrames={minTrackFrames}
                survivorsInClip={survivorsInClip}
                uniqueTracksInClip={uniqueTracksInClip}
                totalDetections={index.totalDetections}
              />
            </span>
          </div>
        ))}
      </div>

      {/* The sampling disclosure. The log reports a band change when the
          re-assessed band differs from the last one reported, and priority is
          re-assessed once a second rather than every frame — otherwise
          detector confidence noise alone produces hundreds of flickers across
          a threshold. Saying so is the difference between a log that is
          sampled and a log that implies the ranking was steady. */}
      <p className="mt-2 shrink-0 text-eyebrow leading-relaxed text-ink-muted">
        Priority re-assessed every {config.event_sample_interval_s}s of
        playback and on every newly confirmed track, not every frame — a score
        wandering across a band threshold in between is not reported. Tracks
        that lasted under{' '}
        {config.min_track_seconds ?? FALLBACK_CONFIG.min_track_seconds}s never
        appear: they are in the raw detections and on the video overlay, not in
        this log. Log clears when the clip is scrubbed backwards.
        {!pinned && ' Scrolled up: not following the clock.'}
      </p>
    </section>
  )
}

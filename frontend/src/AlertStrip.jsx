import { useMemo } from 'react'
import { paint, PRIORITY_BANDS } from './config.js'
import { frameTimecode } from './clock.js'

/**
 * Emergency alerting — what warranted interrupting somebody, and whether it
 * got through.
 *
 * ── Why this is a strip and not a panel ──────────────────────────────
 * App.jsx budgets the space above the fold to four panels that an operator
 * MONITORS, and 1280×720 has no room for a fifth. But alerting is not a thing
 * you watch — it is a thing you need to notice, once, and then act on. A strip
 * is the honest shape for that: one line, always visible, taking its height
 * out of the panels below exactly as the detections error banner does, rather
 * than pushing anything past the fold.
 *
 * ── The sentence this exists to put on screen ────────────────────────
 * "19 queued — no channel configured."
 *
 * That line is the offline-resilience claim, demonstrated instead of asserted.
 * A deck can say the system degrades gracefully without a link; a dashboard
 * that shows a full queue and names the reason it is full has proved it. The
 * three states are kept strictly apart for the same reason:
 *
 *   queued   nobody has tried. There is nowhere to send it.
 *   sent     a channel accepted it.
 *   failed   a channel REFUSED it.
 *
 * Collapsing `failed` into `queued` would let a broken webhook hide behind
 * "we're offline anyway", which is the one failure an alerting system must
 * never conceal.
 *
 * ── Time-gated like everything else ──────────────────────────────────
 * Only alerts whose `frame_id` has been reached are shown, so the strip is a
 * reading of the same playback instant as the map, the queue and the log. An
 * alert for a cluster that forms at t=9.8s must not be on screen at t=2s; the
 * dashboard would be reporting something the footage underneath it has not
 * shown yet.
 *
 * ── Transmit is operator-driven ──────────────────────────────────────
 * The button POSTs; nothing here fires on load. A dashboard that flushed its
 * queue on mount would transmit every time a judge refreshed the page, and the
 * ledger would record deliveries nobody asked for.
 */
export default function AlertStrip({
  alerts,
  alertsError,
  flushResult,
  flushError,
  flushing,
  onFlush,
  config,
  currentFrame,
  selectedTrackId,
  onSelectTrack,
}) {
  // Alerts that have fired by the current frame, newest first — the newest is
  // the one worth a line of screen, and the rest are the counts.
  const fired = useMemo(() => {
    if (!alerts) return null
    return alerts
      .filter((a) => a.frame_id <= currentFrame)
      .slice()
      .sort((a, b) => b.frame_id - a.frame_id)
  }, [alerts, currentFrame])

  const counts = useMemo(() => {
    const tally = { queued: 0, sent: 0, failed: 0 }
    for (const a of fired ?? []) {
      if (a.state in tally) tally[a.state] += 1
    }
    return tally
  }, [fired])

  // ── Loading and failure ────────────────────────────────────────────
  // A failure says the queue is UNREADABLE, never that it is empty. "No
  // alerts" and "cannot tell" are different claims and only one of them would
  // be true, and on this particular strip the false one reads as all-clear.
  if (alertsError) {
    return (
      <Shell tone="hazard">
        <span className="eyebrow shrink-0">Alerting</span>
        <span className="min-w-0 flex-1 truncate text-fine text-ink">
          Alert queue unreadable — this is not an all-clear
        </span>
        <span className="figure shrink-0 text-eyebrow text-ink-muted">
          {alertsError}
        </span>
      </Shell>
    )
  }

  if (fired === null) {
    return (
      <Shell>
        <span className="eyebrow shrink-0">Alerting</span>
        <span className="skeleton h-2.5 w-48" />
      </Shell>
    )
  }

  const newest = fired[0] ?? null
  const pending = counts.queued + counts.failed
  const channel = config?.alert_channel_configured ?? false

  // What the strip SAYS about delivery, in priority order of bad news.
  let status
  let statusTone = 'text-ink-soft'
  if (counts.failed > 0) {
    status = `${counts.failed} failed to send — channel refused`
    statusTone = 'text-ink'
  } else if (!channel) {
    status =
      pending > 0
        ? `${pending} queued — no channel configured`
        : 'No channel configured'
  } else if (pending > 0) {
    status = `${pending} queued — not yet transmitted`
  } else if (counts.sent > 0) {
    status = `${counts.sent} delivered`
  } else {
    status = 'Nothing to send yet'
  }

  return (
    <Shell tone={counts.failed > 0 ? 'hazard' : null}>
      <span className="eyebrow shrink-0">Alerting</span>

      {/* The state of the link, and the queue behind it. */}
      <span className={`shrink-0 text-fine font-semibold ${statusTone}`}>
        {status}
      </span>

      {/* The newest alert to have fired. Clicking it selects the survivor it
          is about, so the strip is a way INTO the map and the queue rather
          than a read-only ticker. Group alerts carry no single track_id and
          are correctly not clickable. */}
      {newest ? (
        <AlertLine
          alert={newest}
          config={config}
          selected={newest.track_id != null && newest.track_id === selectedTrackId}
          onSelect={onSelectTrack}
        />
      ) : (
        <span className="min-w-0 flex-1 text-fine text-ink-muted">
          No alert has fired by this point in the clip
        </span>
      )}

      {/* Counts, always all three, always labelled. A count that disappears
          when it reaches zero makes a reader work out whether the category is
          empty or absent. */}
      <span className="figure shrink-0 text-eyebrow text-ink-muted tabular-nums">
        {counts.queued} queued · {counts.sent} sent · {counts.failed} failed
      </span>

      <button
        type="button"
        onClick={onFlush}
        disabled={flushing || pending === 0}
        title={
          !channel
            ? 'No channel is configured. Transmitting will report that nothing was attempted — it will not mark these as sent.'
            : 'POST every alert not already delivered, highest priority first'
        }
        className="shrink-0 rounded border border-edge bg-surface-0 px-2.5 py-1 text-eyebrow font-semibold tracking-wider text-ink uppercase transition-colors hover:border-ink-muted disabled:cursor-not-allowed disabled:text-ink-muted disabled:hover:border-edge"
      >
        {flushing ? 'Transmitting…' : 'Transmit'}
      </button>

      {/* The result of the last attempt, in the backend's own words. `channel:
          null` is reported as "nothing attempted" rather than as a failure,
          because no delivery was tried — claiming otherwise would invent an
          attempt that never happened. */}
      {(flushResult || flushError) && (
        <span className="figure shrink-0 text-eyebrow text-ink-muted">
          {flushError
            ? `Transmit failed: ${flushError}`
            : flushResult.channel
              ? `${flushResult.sent}/${flushResult.attempted} delivered`
              : (flushResult.note ?? 'nothing attempted')}
        </span>
      )}
    </Shell>
  )
}

/**
 * One alert, rendered as a log line.
 *
 * The band colour is a LEFT GUTTER STRIPE, never the text colour — the same
 * rule the event log follows, and for the same reason: coloured text on a
 * projector is the first thing to wash out, and the word has to carry the
 * meaning on its own.
 */
function AlertLine({ alert, config, selected, onSelect }) {
  const clickable = alert.track_id != null && typeof onSelect === 'function'
  const band = bandForScore(alert.priority, config)

  const body = (
    <>
      <span
        aria-hidden="true"
        className="h-3.5 w-1 shrink-0 rounded-sm"
        style={{ background: band ? paint(band.token) : paint('--ink-muted') }}
      />
      <span className="shrink-0 tabular-nums text-eyebrow text-ink-muted">
        {frameTimecode(alert.frame_id, config?.clip_fps)}
      </span>
      <span className="shrink-0 text-eyebrow font-semibold tracking-wider text-ink-muted uppercase">
        {KIND_LABELS[alert.kind] ?? alert.kind}
      </span>
      <span className="min-w-0 truncate text-fine text-ink">{alert.detail}</span>
    </>
  )

  if (!clickable) {
    return <span className="flex min-w-0 flex-1 items-center gap-2">{body}</span>
  }

  return (
    <button
      type="button"
      onClick={() => onSelect(alert.track_id)}
      aria-pressed={selected}
      className={`flex min-w-0 flex-1 items-center gap-2 rounded px-1.5 py-0.5 text-left transition-colors hover:bg-surface-2 ${
        selected ? 'bg-surface-2' : ''
      }`}
    >
      {body}
    </button>
  )
}

const KIND_LABELS = {
  critical_survivor: 'Critical',
  cluster: 'Cluster',
  hazard_proximity: 'Hazard',
}

/**
 * The band a raw score falls in.
 *
 * `Alert` carries the score but not the band — the band is the survivor's
 * property and an alert is an event about one. Rather than widen the schema,
 * the cut points come from `/api/config`, which is where every other band
 * boundary on this dashboard comes from. Null for a group alert, which has no
 * single score; the stripe then falls back to muted ink rather than picking a
 * band nobody computed.
 */
function bandForScore(score, config) {
  if (typeof score !== 'number' || !config) return null
  if (score >= config.priority_critical_at) return PRIORITY_BANDS.critical
  if (score >= config.priority_high_at) return PRIORITY_BANDS.high
  if (score >= config.priority_medium_at) return PRIORITY_BANDS.medium
  return PRIORITY_BANDS.low
}

/** The strip's box. `shrink-0` so it takes its height out of the panels. */
function Shell({ tone, children }) {
  return (
    <div
      className={`flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border bg-surface-1 px-4 py-2 ${
        tone === 'hazard' ? 'border-hazard' : 'border-edge'
      }`}
    >
      {children}
    </div>
  )
}

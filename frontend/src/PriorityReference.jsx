import { PRIORITY_RAMP, paint } from './config.js'

/**
 * The priority ramp, explained — reference material, not state.
 *
 * This is the half of the survivor panel that never changes while the clip
 * plays: what the four colours mean, where their cut points are, and the
 * formula the scores come out of. It used to sit under the priority queue and
 * cost that panel about a hundred vertical pixels it needed for rows.
 *
 * It reads once. Nobody watches it. So it lives below the fold in a collapsed
 * disclosure, where the four operational panels are not paying for it — and
 * nothing on those panels depends on it being open, because every row and
 * every log line already spells its band out in words beside the swatch.
 *
 * Every number here still comes from `/api/config`: editing `backend/config.py`
 * edits this section. A judge asking how the ranking works reads the answer off
 * the screen rather than being told it.
 */

/**
 * The ramp itself, in rank order.
 *
 * A legend earns its place because the ramp is ordinal: four swatches in a row,
 * lightest to darkest, is what shows a reader that the colours are a SEQUENCE
 * rather than four unrelated statuses. Read from `PRIORITY_RAMP`, which is
 * sorted by rank, so the legend cannot end up in a different order from the
 * scale it documents.
 */
function RampLegend({ config }) {
  const cuts = {
    low: `below ${config.priority_medium_at.toFixed(2)}`,
    medium: `${config.priority_medium_at.toFixed(2)} and above`,
    high: `${config.priority_high_at.toFixed(2)} and above`,
    critical: `${config.priority_critical_at.toFixed(2)} and above`,
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      {PRIORITY_RAMP.map((band) => (
        <span key={band.name} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-3 w-3 shrink-0 rounded-sm"
            style={{ backgroundColor: paint(band.token) }}
          />
          <span className="text-fine font-semibold text-ink-soft">{band.label}</span>
          <span className="figure text-eyebrow text-ink-muted">{cuts[band.name]}</span>
        </span>
      ))}
    </div>
  )
}

/**
 * @param {object} props
 * @param {object} props.config clip constants in force right now
 */
export default function PriorityReference({ config }) {
  return (
    <div className="flex flex-col gap-3">
      <RampLegend config={config} />

      {/* The formula, on screen, in the numbers actually in force. */}
      <p className="text-eyebrow leading-relaxed text-ink-muted">
        Priority is a weighted average of detection confidence (
        <span className="figure text-ink-soft">{config.weight_confidence}</span>), cluster
        size — survivors within{' '}
        <span className="figure text-ink-soft">{config.cluster_radius_m} m</span> (
        <span className="figure text-ink-soft">{config.weight_cluster_size}</span>), and
        hazard proximity (
        <span className="figure text-ink-soft">{config.weight_hazard_proximity}</span>).{' '}
        {config.hazard_count > 0 ? (
          <>
            Scored against{' '}
            <span className="figure text-ink-soft">{config.hazard_count}</span> known hazard{' '}
            {config.hazard_count === 1 ? 'position' : 'positions'}.
          </>
        ) : (
          <>
            The hazard term is <span className="text-ink-soft">not scored</span> — hazard
            classification is Phase 2, so there is no hazard layer yet and the other two
            weights are renormalised. That is not a claim that the area is clear.
          </>
        )}{' '}
        The four bands above are the quarters of the 0–1 score range — a ranking, not four
        statuses. There is no &ldquo;clear&rdquo; band and nothing in the ramp is green,
        because every row in the priority queue is someone who still needs reaching.
        Select a row to highlight that survivor on the map and in the video.
      </p>

    </div>
  )
}

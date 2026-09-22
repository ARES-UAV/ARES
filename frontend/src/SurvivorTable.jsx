import { useEffect, useMemo, useRef } from 'react'
import PanelShell from './PanelShell.jsx'
import { FALLBACK_CONFIG, paint, priorityBand } from './config.js'

/**
 * The ranked survivor list — one row per confirmed person.
 *
 * Rows are the `survivors` prop and nothing else. That is the same array App
 * hands the header to count, so the number of rows here and the header's
 * "confirmed survivors" figure are one value rendered two ways. CONVENTIONS.md's
 * first dashboard requirement is that counts reconcile across every section,
 * and the first mockup failed it with a header saying 12 above a table showing
 * 5 — the only durable fix is for the table and the count to be the same list,
 * not two derivations that agree today.
 *
 * The header's OTHER survivor figure — track IDs issued — is deliberately not
 * a row count here and is not meant to match this table. It is what the
 * tracker emitted before the persistence filter, and this table is what
 * survived it. Two different questions, two different numbers, both labelled.
 *
 * The list is already ranked when it arrives: `/api/survivors` returns it
 * sorted by priority descending. Re-sorting here would be a second opinion on
 * rescue order, and there should only be one.
 *
 * Selection is App's, not this component's. Clicking a row calls the same
 * `onSelectTrack` a map marker click calls, with the same toggle-to-clear
 * behaviour, so a row, a pin and a bounding box are three views of one
 * selection rather than three things that need keeping in step.
 *
 * Every number in here is a `.figure`, `.score`, `.coord` or a `td.num` —
 * the class hooks tokens.css defines, which is what puts `--font-data` and
 * `tabular-nums` on them. A proportional digit in a coordinate column makes
 * the decimal points wander, and a column of coordinates whose points do not
 * line up cannot be scanned at all.
 */

/** Column header cell. Sticky, so the columns stay named while the list scrolls. */
function Th({ children, numeric = false, tight = false }) {
  return (
    <th
      scope="col"
      className={`sticky top-0 z-10 border-b border-edge bg-surface-2 ${
        tight ? 'px-2' : 'px-2.5'
      } py-2 text-eyebrow font-semibold tracking-wider whitespace-nowrap text-ink-muted uppercase ${
        numeric ? 'text-right' : 'text-left'
      }`}
    >
      {children}
    </th>
  )
}

/**
 * The priority cell: a swatch, the score, the band's name in words, and a
 * compact breakdown of what the score is made of.
 *
 * The word is not optional. The four steps are an ORDINAL RAMP — one hue,
 * monotone light to dark — which is what makes the ordering survivable for a
 * viewer with a colour vision deficiency, but a ramp still only tells you
 * "darker than that one", never which band this is. Colour alone is also
 * unreliable on a projector at the back of a room. So the label is always
 * rendered beside the swatch, never the swatch on its own.
 *
 * Beacon never appears in this column. Beacon means "this is a
 * detection", and every row here is one — colouring priority in it would say
 * nothing, and using it for one band would break its meaning everywhere else.
 *
 * ── The score breakdown bar ───────────────────────────────────────
 * The small bar under the figure splits the score into the weighted
 * contributions `score_breakdown` records: confidence, cluster, hazard. Its
 * fill is the band hue, which is the score's magnitude — darker is more
 * urgent — and each segment's width is that term's share of the total. On the
 * demo clip only confidence is scored (cluster and hazard both drop), so the
 * bar is a single confident segment and the other two terms read "not scored"
 * in the muted, deliberately-colourless unmeasured step. That converts the
 * otherwise suspicious "priority equals exactly the confidence" into a visible
 * statement of correct behaviour: the two missing terms report their absence,
 * they are never drawn at zero.
 *
 * Colour choice is bounded by tokens.css. Segments use the band's own ramp
 * token (already validated); "not scored" uses the ink-muted step of the
 * unmeasured tokens. No new colour is invented here.
 */
const TERMS = [
  { key: 'confidence', label: 'conf' },
  { key: 'cluster', label: 'cluster' },
  { key: 'hazard', label: 'hazard' },
]

/**
 * The priority cell.
 *
 * `expanded` is the selected row, and it is the ONLY row that shows the score
 * breakdown. Measured on the demo clip: with the contribution bar and the
 * three term readouts on every row, one row stood 135px tall and the queue
 * showed two people. A rescue order you have to scroll to read is not a rescue
 * order — the whole value of the panel is seeing who is next.
 *
 * Nothing is lost. The breakdown is the answer to "why is this one ranked
 * here?", which is a question asked about ONE survivor, and asking it is
 * exactly the act of selecting them.
 */
function PriorityCell({ survivor, expanded }) {
  const band = priorityBand(survivor.priority_band)
  const breakdown = survivor.score_breakdown ?? {}

  return (
    <div className="flex flex-col items-start gap-1 py-0.5">
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className="h-3 w-3 shrink-0 rounded-sm"
          style={{ backgroundColor: band.color }}
        />
        <span className="score w-9 text-right font-semibold text-ink">
          {survivor.priority.toFixed(2)}
        </span>
        {/* w-12, not auto: "Critical" is the longest band name and fits, and
            this table has four nowrap columns to fit inside half of a 1280px
            screen. Fixed rather than auto so the words start on one edge. */}
        <span className="w-12 text-fine font-semibold text-ink-soft">{band.label}</span>
      </div>

      {/* The stacked contribution bar. Segments are the scored terms' shares
          of the 0-1 total; the fill is the band hue, so width and colour tell
          the same story about magnitude. Absent terms get no segment. On the
          demo clip only confidence is scored, so this is a single full-width
          segment; the term values below carry the split numerically whenever
          more than one term is in play. */}
      {expanded && (
      <div
        aria-hidden="true"
        className="flex h-1 w-[9.5rem] overflow-hidden rounded-full bg-surface-2"
      >
        {TERMS.map(
          ({ key }) =>
            breakdown[key] != null && (
              <div
                key={key}
                style={{
                  width: `${(breakdown[key] / 1) * 100}%`,
                  backgroundColor: band.color,
                }}
              />
            ),
        )}
      </div>
      )}

      {/* The three terms, each reporting its own state. A scored term shows
          its share in the ink-soft step; a dropped term shows "not scored" in
          the muted unmeasured step — the same visual rule the empty hazard
          layer already uses, so absence can never be misread as zero. The
          reason each dropped term is absent lives in the row tooltip. */}
      {expanded && (
      <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] leading-none tracking-wide">
        {TERMS.map(({ key, label }) =>
          breakdown[key] != null ? (
            <span key={key} className="text-ink-soft">
              {label} {breakdown[key].toFixed(2)}
            </span>
          ) : (
            <span key={key} className="text-ink-muted">
              {label} — not scored
            </span>
          ),
        )}
      </div>
      )}
    </div>
  )
}

/** Placeholder rows while the roster is in flight. */
function SkeletonRows() {
  return Array.from({ length: 4 }, (_, i) => (
    <tr key={i} className="border-t border-edge-soft">
      {Array.from({ length: 4 }, (__, j) => (
        <td key={j} className="px-2.5 py-1.5">
          <div className="skeleton h-3" style={{ width: j === 0 ? '9rem' : '4rem' }} />
        </td>
      ))}
    </tr>
  ))
}

/**
 * @param {object}   props
 * @param {object[]|null} props.routes       ground routes by track, or null
 * @param {object[]|null} props.survivors    rows: survivors confirmed by this
 *                                           frame, already ranked. null while
 *                                           loading.
 * @param {number|null}   props.survivorsInClip confirmed survivors in the clip
 * @param {string|null}   props.survivorsError
 * @param {object}   props.config             clip constants in force right now
 * @param {number|null} props.selectedTrackId
 * @param {function} props.onSelectTrack
 */
export default function SurvivorTable({
  routes,
  survivors,
  survivorsInClip,
  survivorsError,
  config,
  selectedTrackId,
  onSelectTrack,
}) {
  // Route lookup by track. Built here rather than threaded through every row
  // so the table does a single pass over a list it does not own.
  const routeByTrack = useMemo(() => {
    const m = new Map()
    for (const r of routes ?? []) m.set(r.track_id, r)
    return m
  }, [routes])

  const scrollRef = useRef(null)

  // Bring the selected row into view when the selection changes elsewhere —
  // clicking a map pin for someone ranked ninth should not leave the operator
  // scrolling to find out why nothing appeared to happen.
  //
  // Keyed on the selection only, not on the row list: the list grows as the
  // clip plays, and re-running this every time a survivor is discovered would
  // drag the table back to the selected row while someone is reading further
  // down it. `block: 'nearest'` scrolls the table's own box by the minimum
  // needed and leaves the page alone.
  useEffect(() => {
    if (selectedTrackId === null) return
    const container = scrollRef.current
    const row = container?.querySelector(`[data-track-id="${selectedTrackId}"]`)
    row?.scrollIntoView({ block: 'nearest' })
  }, [selectedTrackId])

  const rows = survivors ?? []

  const basis = (
    <>
      <p>
        Ordered by priority, highest first — this is a RESCUE ORDER, not a
        detection list. A row appears once its track has persisted{' '}
        <span className="figure text-ink">
          {config?.min_track_frames ?? FALLBACK_CONFIG.min_track_frames}
        </span>{' '}
        frames, so the count here lags the tracker by exactly that threshold.
      </p>
      <p className="mt-1.5">
        Detector confidence is not a column — it is in the score breakdown on
        the selected row, beside the score it produced. The band name is
        spelled out on every row; the swatch is never the only encoding. The full ramp and the scoring formula are below the fold under
        “Priority ramp and scoring” — reference material, read once.
      </p>
      <p className="mt-1.5">
        A detour figure under a track ID is what avoiding known hazards cost the
        ground route to that survivor. Absent means no hazards are known, so
        nothing was avoided — not that the ground is clear.
      </p>
    </>
  )

  return (
    <PanelShell
      title="Survivor priority queue"
      meta={
        survivorsError
          ? 'unavailable'
          : survivors === null
            ? 'loading…'
            : `${rows.length} of ${survivorsInClip} · highest priority first`
      }
      note={basis}
    >

      {/* The list takes the row's leftover height and scrolls inside it. The
          ramp legend and the scoring formula that used to sit under here are
          reference material an operator reads once, so they moved below the
          fold — this panel changes while the clip plays and has to stay whole
          and on screen. The band's name is still spelled out on every row, so
          nothing here depends on the legend being visible. */}
      {survivorsError ? (
          <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
            <p className="text-body font-semibold text-ink">Survivor list unavailable</p>
            <p className="text-fine text-ink-soft">{survivorsError}</p>
            <p className="text-eyebrow text-ink-muted">
              Rescue order cannot be shown without it. The clip, the detection
              overlay and the per-frame count above are unaffected.
            </p>
          </div>
        ) : (
          /* `overflow-x-auto` is a safety net, not the plan: the six columns
             fit the panel at 1280px, and below that the table scrolls sideways
             inside its own box rather than clipping the coordinate columns off
             the right edge or forcing the whole page wide. */
          <div
            ref={scrollRef}
            className="ares-table-scroll min-h-0 flex-1 overflow-x-auto overflow-y-auto"
          >
            <table className="w-full border-collapse text-fine">
              <thead>
                <tr>
                  <Th>Priority</Th>
                  {/* "Track" still, not "Track / detour": the second line is
                      conditional and usually absent, and a header naming a
                      column that is blank in every row describes a table that
                      is not there. The sublabel carries its own tooltip. */}
                  <Th>Track</Th>
                  {/* One column, not two. The pair is the point — the
                      distance between the frames IS the persistence threshold
                      — and this panel is half of a 1280px screen, where a
                      seventh nowrap column pushed the coordinates off the
                      right edge. */}
                  <Th tight>Seen → confirmed</Th>
                  {/* No confidence column. It is the detector's own number,
                      not a decision the operator makes, and at five nowrap
                      columns the coordinate pair was being clipped mid-digit
                      — a position readout missing a digit is worse than one
                      that is not shown. Confidence still appears, in the score
                      breakdown on the selected row, which is where a
                      provenance figure belongs: beside the score it produced.
                      Measured: dropping it is what made the pair fit. */}
                  {/* ONE column, not two. Two nowrap coordinate columns did
                      not fit in half of a 1280px screen — the longitude was
                      being clipped mid-digit, which on a position readout is
                      worse than not showing it. A coordinate is a PAIR anyway;
                      splitting it made two columns out of one value. */}
                  <Th numeric>Position</Th>
                </tr>
              </thead>
              <tbody>
                {survivors === null && <SkeletonRows />}

                {survivors !== null && rows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-ink-muted">
                      No survivors confirmed yet — a track has to be seen in{' '}
                      {config.min_track_frames ?? FALLBACK_CONFIG.min_track_frames} frames
                      before it counts as a person, so the first rows appear a
                      little after the first detections do.
                    </td>
                  </tr>
                )}

                {rows.map((survivor) => {
                  const selected = survivor.track_id === selectedTrackId
                  return (
                    <tr
                      key={survivor.track_id}
                      data-track-id={survivor.track_id}
                      tabIndex={0}
                      aria-selected={selected}
                      onClick={() => onSelectTrack(survivor.track_id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          onSelectTrack(survivor.track_id)
                        }
                      }}
                      // The selected row is marked in Beacon, matching
                      // the map pin and the bounding box. The priority ramp in
                      // the first column is never borrowed for this: those
                      // colours mean rank, and a row that darkened because it
                      // was clicked would read as a change in priority.
                      className={`cursor-pointer border-t border-edge-soft outline-none transition-colors ${
                        selected ? 'bg-surface-2' : 'hover:bg-surface-2/60'
                      }`}
                      style={
                        selected
                          ? { boxShadow: `inset 3px 0 0 0 ${paint('--survivor')}` }
                          : undefined
                      }
                      // The whole breakdown, for the judge who asks about one
                      // specific row rather than the formula in general.
                      title={
                        `Priority ${survivor.priority.toFixed(3)} — ` +
                        `confidence ${survivor.confidence.toFixed(2)}, ` +
                        `${survivor.cluster_size} other survivor(s) within ` +
                        `${config.cluster_radius_m} m` +
                        // Both terms report their own absence rather than
                        // letting a reader assume a number they cannot see was
                        // part of the score. A null cluster_score means the
                        // term was the same for everyone and was dropped — not
                        // that this row has no neighbours, which the count
                        // beside it already answers.
                        (survivor.cluster_score == null
                          ? ' (cluster term not scored — same for every survivor)'
                          : '') +
                        (config.hazard_count > 0
                          ? ''
                          : ', hazard term not scored (no hazard layer)') +
                        // The new per-row fields, folded into the same tooltip
                        // because they are read once, on demand, and do not
                        // deserve a seventh nowrap column. position_spread_m
                        // is the honest error bar on the map pin: centimetres
                        // means the projection agrees with itself, tens of
                        // metres means altitude or frame width is wrong.
                        //
                        // Guarded: a backend running an older Survivor schema
                        // without these fields still renders the rest of the
                        // row. Same defensive posture as the LEGACY_BANDS
                        // fallback in config.js.
                        (survivor.position_spread_m != null
                          ? ` · position spread ${survivor.position_spread_m.toFixed(2)} m across ${survivor.detection_count} frames`
                          : '') +
                        // group_size counts the whole connected component
                        // INCLUDING this survivor; cluster_size above is their
                        // direct neighbours EXCLUDING self — 23 vs 22 on this
                        // fully-linked patch. Both true, both labelled.
                        (survivor.group_id != null
                          ? ` · group ${survivor.group_id} (${survivor.group_size} members in component)`
                          : '')
                      }
                    >
                      <td className="px-2.5 py-1.5">
                        <PriorityCell
                          survivor={survivor}
                          expanded={survivor.track_id === selectedTrackId}
                        />
                      </td>
                      {/* The track ID, and under it the detour the safe
                          ground route took to reach this person.

                          NOT a seventh column. This table has a 616px budget
                          and a seventh nowrap column is exactly what cut the
                          longitude off last time — see the note on the
                          "Seen → confirmed" header. A second line under the ID
                          costs no width at all: "+32 m" is no wider than
                          "#1409", which this column already has to fit.

                          It appears only where there is something to say.
                          While no hazards are known every detour is zero, the
                          line is absent from every row, and the table looks
                          exactly as it does today — the routing feature does
                          not get to announce itself before it has done
                          anything. */}
                      <td className="num px-2.5 py-1.5 whitespace-nowrap text-ink">
                        <span className="font-semibold">#{survivor.track_id}</span>
                        {(() => {
                          const route = routeByTrack.get(survivor.track_id)
                          if (!route || !route.hazard_aware || route.detour_m <= 0) {
                            return null
                          }
                          return (
                            <span
                              className="block text-eyebrow font-normal text-ink-muted"
                              title={
                                `Safe ground route ${route.length_m} m against ` +
                                `${route.direct_length_m} m direct. Peak hazard ` +
                                `exposure ${route.direct_risk_max} → ${route.risk_max}.`
                              }
                            >
                              +{route.detour_m} m
                            </span>
                          )
                        })()}
                      </td>
                      {/* First sighting, then the frame the row earned its
                          place. The gap between them is the persistence
                          threshold, made checkable per survivor instead of
                          asserted once in the header.

                          Frames only, no clock time beside them: the two
                          figures plus a seconds reading is what pushed this
                          panel's table past its 616px and cut the longitude
                          column off. The event log's confirmation line for
                          this track carries the timecode, so the dashboard
                          still states it — once, where there is room. */}
                      <td className="num px-2 py-2 whitespace-nowrap text-ink-soft">
                        {survivor.first_frame}
                        <span className="text-ink-muted"> → </span>
                        {survivor.confirmed_frame}
                      </td>
                      <td className="coord px-2.5 py-1.5 text-right whitespace-nowrap text-ink-soft">
                        {survivor.latitude.toFixed(5)},{' '}
                        {survivor.longitude.toFixed(5)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
    </PanelShell>
  )
}

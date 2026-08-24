import { useEffect, useRef } from 'react'
import { paint, priorityBand } from './config.js'

/**
 * The ranked survivor list — one row per de-duplicated person.
 *
 * Rows are the `survivors` prop and nothing else. That is the same array App
 * hands the header to count, so the number of rows here and the header's
 * "survivors tracked" figure are one value rendered two ways. CLAUDE.md's
 * first dashboard requirement is that counts reconcile across every section,
 * and the first mockup failed it with a header saying 12 above a table showing
 * 5 — the only durable fix is for the table and the count to be the same list,
 * not two derivations that agree today.
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
function Th({ children, numeric = false }) {
  return (
    <th
      scope="col"
      className={`sticky top-0 z-10 border-b border-edge bg-surface-2 px-3 py-2 text-eyebrow font-semibold tracking-wider whitespace-nowrap text-ink-muted uppercase ${
        numeric ? 'text-right' : 'text-left'
      }`}
    >
      {children}
    </th>
  )
}

/**
 * The priority cell: a swatch, the score, and the band's name in words.
 *
 * The word is not optional. The four steps are an ORDINAL RAMP — one hue,
 * monotone light to dark — which is what makes the ordering survivable for a
 * viewer with a colour vision deficiency, but a ramp still only tells you
 * "darker than that one", never which band this is. Colour alone is also
 * unreliable on a projector at the back of a room. So the label is always
 * rendered beside the swatch, never the swatch on its own.
 *
 * Survivor cyan never appears in this column. Cyan means "this is a
 * detection", and every row here is one — colouring priority in it would say
 * nothing, and using it for one band would break its meaning everywhere else.
 */
function PriorityCell({ survivor }) {
  const band = priorityBand(survivor.priority_band)

  return (
    <div className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className="h-3 w-3 shrink-0 rounded-sm"
        style={{ backgroundColor: band.color }}
      />
      <span className="score w-9 text-right font-semibold text-ink">
        {survivor.priority.toFixed(2)}
      </span>
      <span className="w-16 text-fine font-semibold text-ink-soft">{band.label}</span>
    </div>
  )
}

/** Placeholder rows while the roster is in flight. */
function SkeletonRows() {
  return Array.from({ length: 4 }, (_, i) => (
    <tr key={i} className="border-t border-edge-soft">
      {Array.from({ length: 6 }, (__, j) => (
        <td key={j} className="px-3 py-2.5">
          <div className="skeleton h-3" style={{ width: j === 0 ? '9rem' : '4rem' }} />
        </td>
      ))}
    </tr>
  ))
}

/**
 * @param {object}   props
 * @param {object[]|null} props.survivors    rows: survivors found by this frame,
 *                                           already ranked. null while loading.
 * @param {number|null}   props.survivorsInClip total tracks in the whole clip
 * @param {string|null}   props.survivorsError
 * @param {object}   props.config             clip constants in force right now
 * @param {number|null} props.selectedTrackId
 * @param {function} props.onSelectTrack
 */
export default function SurvivorTable({
  survivors,
  survivorsInClip,
  survivorsError,
  config,
  selectedTrackId,
  onSelectTrack,
}) {
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

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex shrink-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="eyebrow">Survivor priority queue</h2>
        {/* Same prop as the rows and as the header's survivor count. Not a
            separate tally that has to be checked against them. */}
        <span className="figure text-eyebrow text-ink-muted">
          {survivorsError
            ? 'unavailable'
            : survivors === null
              ? 'loading…'
              : `${rows.length} of ${survivorsInClip} found by this frame · highest priority first`}
        </span>
      </div>

      {/* The list takes the row's leftover height and scrolls inside it. The
          ramp legend and the scoring formula that used to sit under here are
          reference material an operator reads once, so they moved below the
          fold — this panel changes while the clip plays and has to stay whole
          and on screen. The band's name is still spelled out on every row, so
          nothing here depends on the legend being visible. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-edge">
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
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full border-collapse text-fine">
              <thead>
                <tr>
                  <Th>Priority</Th>
                  <Th>Track</Th>
                  <Th>First seen</Th>
                  <Th numeric>Confidence</Th>
                  <Th numeric>Latitude</Th>
                  <Th numeric>Longitude</Th>
                </tr>
              </thead>
              <tbody>
                {survivors === null && <SkeletonRows />}

                {survivors !== null && rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-ink-muted">
                      No survivors found yet — rows appear as the clip reaches them.
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
                      // The selected row is marked in survivor cyan, matching
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
                        `${survivor.cluster_size} survivor(s) within ` +
                        `${config.cluster_radius_m} m` +
                        (config.hazard_count > 0
                          ? ''
                          : ', hazard term not scored (no hazard layer)')
                      }
                    >
                      <td className="px-3 py-2">
                        <PriorityCell survivor={survivor} />
                      </td>
                      <td className="num px-3 py-2 font-semibold whitespace-nowrap text-ink">
                        #{survivor.track_id}
                      </td>
                      <td className="num px-3 py-2 whitespace-nowrap text-ink-soft">
                        frame {survivor.first_frame}
                        <span className="ml-1.5 text-ink-muted">
                          {(survivor.first_frame / config.clip_fps).toFixed(1)} s
                        </span>
                      </td>
                      <td className="num px-3 py-2 text-right whitespace-nowrap text-ink-soft">
                        {survivor.confidence.toFixed(2)}
                      </td>
                      <td className="coord px-3 py-2 text-right whitespace-nowrap text-ink-soft">
                        {survivor.latitude.toFixed(5)}
                      </td>
                      <td className="coord px-3 py-2 text-right whitespace-nowrap text-ink-soft">
                        {survivor.longitude.toFixed(5)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </section>
  )
}

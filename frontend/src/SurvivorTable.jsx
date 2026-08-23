import { useEffect, useRef } from 'react'
import { COLORS, priorityBand } from './config.js'

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
 */

/** Column header cell. Sticky, so the columns stay named while the list scrolls. */
function Th({ children }) {
  return (
    <th
      scope="col"
      className="sticky top-0 z-10 whitespace-nowrap bg-slate-900 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-400"
    >
      {children}
    </th>
  )
}

/**
 * The priority cell: a swatch, the score, and the band's name in words.
 *
 * The word is not optional. Colour alone is unreadable to anyone with a colour
 * vision deficiency and unreliable on a projector at the back of a room, so
 * the ramp always carries its label (CLAUDE.md's dashboard review, and the
 * reason survivor cyan never appears in this column — cyan means survivor, and
 * every row here is one).
 */
function PriorityCell({ survivor }) {
  const band = priorityBand(survivor.priority_band)

  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="h-2.5 w-2.5 shrink-0 rounded-sm"
        style={{ backgroundColor: band.color }}
      />
      <span className="w-9 text-right font-semibold tabular-nums text-slate-100">
        {survivor.priority.toFixed(2)}
      </span>
      <span
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: band.color }}
      >
        {band.label}
      </span>
    </div>
  )
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
    <section className="flex flex-col">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Survivor priority queue
        </h2>
        {/* Same prop as the rows and as the header's survivor count. Not a
            separate tally that has to be checked against them. */}
        <span className="text-[11px] tabular-nums text-slate-500">
          {survivorsError
            ? 'unavailable'
            : survivors === null
              ? 'loading…'
              : `${rows.length} of ${survivorsInClip} found by this frame · highest priority first`}
        </span>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-800">
        {survivorsError ? (
          <p className="px-4 py-6 text-center text-sm text-slate-400">
            Could not load the survivor list — {survivorsError}
          </p>
        ) : (
          <div ref={scrollRef} className="max-h-[22rem] overflow-y-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  <Th>Priority</Th>
                  <Th>Track</Th>
                  <Th>First seen</Th>
                  <Th>Confidence</Th>
                  <Th>Latitude</Th>
                  <Th>Longitude</Th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                      {survivors === null
                        ? 'Loading survivor positions…'
                        : 'No survivors found yet — rows appear as the clip reaches them.'}
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
                      // the map pin and the bounding box. The priority colours
                      // in the first column are never borrowed for this: they
                      // mean escalation, and a row that turned orange because
                      // it was clicked would read as a change in priority.
                      className={`cursor-pointer border-t border-slate-800/80 outline-none transition-colors ${
                        selected ? 'bg-slate-800/80' : 'hover:bg-slate-900'
                      } focus-visible:bg-slate-800`}
                      style={
                        selected
                          ? { boxShadow: `inset 3px 0 0 0 ${COLORS.survivor}` }
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
                      <td className="whitespace-nowrap px-3 py-2 font-semibold tabular-nums text-slate-200">
                        #{survivor.track_id}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-400">
                        frame {survivor.first_frame}
                        <span className="ml-1.5 text-slate-600">
                          {(survivor.first_frame / config.clip_fps).toFixed(1)} s
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-300">
                        {survivor.confidence.toFixed(2)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-300">
                        {survivor.latitude.toFixed(5)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-300">
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

      {/* The formula, on screen, in the numbers actually in force — they come
          from /api/config, so changing backend/config.py changes this sentence.
          A judge asking how the ranking works should be able to read the answer
          rather than be told it. */}
      <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
        Priority is a weighted average of detection confidence (
        <span className="tabular-nums text-slate-400">{config.weight_confidence}</span>),
        cluster size — survivors within{' '}
        <span className="tabular-nums text-slate-400">{config.cluster_radius_m} m</span> (
        <span className="tabular-nums text-slate-400">{config.weight_cluster_size}</span>
        ), and hazard proximity (
        <span className="tabular-nums text-slate-400">
          {config.weight_hazard_proximity}
        </span>
        ).{' '}
        {config.hazard_count > 0 ? (
          <>
            Scored against{' '}
            <span className="tabular-nums text-slate-400">{config.hazard_count}</span> known
            hazard {config.hazard_count === 1 ? 'position' : 'positions'}.
          </>
        ) : (
          <>
            The hazard term is <span className="text-slate-400">not scored</span> — hazard
            classification is Phase 2, so there is no hazard layer yet and the other two
            weights are renormalised. That is not a claim that the area is clear.
          </>
        )}{' '}
        Bands: <span style={{ color: COLORS.critical }}>critical</span> ≥{' '}
        <span className="tabular-nums text-slate-400">
          {config.priority_critical_at.toFixed(2)}
        </span>
        , <span style={{ color: COLORS.serious }}>serious</span> ≥{' '}
        <span className="tabular-nums text-slate-400">
          {config.priority_serious_at.toFixed(2)}
        </span>
        , <span style={{ color: COLORS.warning }}>warning</span> below that — there is no
        &ldquo;clear&rdquo; band, because every row here is someone who still needs
        reaching. Select a row to highlight that survivor on the map and in the video.
      </p>
    </section>
  )
}

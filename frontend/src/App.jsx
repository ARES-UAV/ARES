import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchDetections, fetchEvents, fetchSurvivors, loadConfig } from './api.js'
import { buildDetectionIndex, detectionsAt } from './detectionIndex.js'
import EventLogPanel from './EventLogPanel.jsx'
import HeaderBar from './HeaderBar.jsx'
import MapPanel from './MapPanel.jsx'
import MissionParameters from './MissionParameters.jsx'
import PriorityReference from './PriorityReference.jsx'
import SurvivorTable from './SurvivorTable.jsx'
import VideoPanel from './VideoPanel.jsx'

/**
 * ARES command dashboard.
 *
 * The shared state lives here and nowhere else:
 *
 *   config       — clip and camera constants, fetched from the backend. Falls
 *                  back to the bundled copy in config.js when the backend is
 *                  unreachable, and the header shows an offline badge when it
 *                  does. Panels are handed it rather than importing constants,
 *                  so there is one set of numbers in force at any moment.
 *
 *   detections   — the whole clip's records, fetched once. The per-frame
 *                  detection count and the video overlay both read the index
 *                  built from it, so "3 in frame" in the header and three boxes
 *                  on the video are the same lookup.
 *
 *   survivors    — one record per unique track_id, already ranked by priority
 *                  descending, each with a lat/lon and a priority score the
 *                  backend derived. This is a *view* of the same detections
 *                  file, not a second dataset.
 *
 *   events       — the clip's cluster and priority-band timeline, from
 *                  `/api/events`. The half of the mission log that needs the
 *                  server's localization and scoring; the other half is
 *                  derived from `survivors` below, so the log's acquisition
 *                  lines are the survivor roster rather than a second count of
 *                  it. See missionLog.js.
 *
 *   clipDuration — the clip's true length in seconds, reported up by the video
 *                  element once its metadata lands. Held here because two
 *                  panels are readings of it: the scrubber's range, and the
 *                  frame the event log calls the end of the clip.
 *
 *   currentFrame — the playback clock. VideoPanel derives it from the video's
 *                  currentTime and reports it up; the map, survivor table and
 *                  anything else time-varying read it from here, so the whole
 *                  dashboard is always showing the same instant.
 *
 *   selectedTrackId — which survivor the operator is looking at. Owned here
 *                  because it crosses three panels: a map pin, a table row and
 *                  a bounding box are one selection viewed three ways, and the
 *                  map and the table set it with the same handler.
 *
 * Everything derived from that state is derived HERE, once, and passed down.
 * Panels are given numbers and lists, never the raw data to tally for
 * themselves — a panel that counts for itself is a panel that can disagree
 * with the header, which was the first mockup's worst flaw.
 */
export default function App() {
  const [config, setConfig] = useState(null)
  const [configOffline, setConfigOffline] = useState(false)
  const [detections, setDetections] = useState(null)
  const [survivors, setSurvivors] = useState(null)
  const [survivorsError, setSurvivorsError] = useState(null)
  const [events, setEvents] = useState(null)
  const [eventsError, setEventsError] = useState(null)
  const [clipDuration, setClipDuration] = useState(0)
  const [error, setError] = useState(null)
  const [currentFrame, setCurrentFrame] = useState(0)
  const [selectedTrackId, setSelectedTrackId] = useState(null)

  // ── The fold ─────────────────────────────────────────────────────
  // The four operational panels have to be reachable without scrolling at
  // 1280×720, which is projector resolution and the only size that actually has
  // to work. So the block that holds them is given exactly the space between
  // the bottom of the header and the fold, and the panels divide it up.
  //
  // The header's height is MEASURED rather than assumed. It wraps differently
  // at different widths and its stat strip can grow by a line; a hard-coded
  // 7rem would be right at 1280 and quietly push the event log off the bottom
  // somewhere else. One ResizeObserver removes the whole class of problem.
  //
  // A CALLBACK ref, not a ref object watched by an effect. The header does not
  // exist on first render — the skeleton below is returned instead — so a
  // `useEffect(..., [])` would run once against a null ref, never run again,
  // and leave the height at 0 forever. That failure is quiet and nasty: the
  // block below would be a full `100vh` tall and push the bottom row clean off
  // the screen, which is the exact thing this measurement exists to prevent.
  // A callback ref fires when the node actually arrives. React 19 runs the
  // function it returns as the detach cleanup.
  const [headerHeight, setHeaderHeight] = useState(0)

  const measureHeader = useCallback((element) => {
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      // borderBoxSize, not contentRect: the header has a bottom border and the
      // block below it starts under the border, not under the content.
      const box = entry.borderBoxSize?.[0]
      setHeaderHeight(box ? box.blockSize : entry.contentRect.height)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    // Never rejects — it degrades to the bundled constants and reports that it
    // did. See loadConfig in api.js.
    loadConfig().then(({ config: loaded, offline }) => {
      setConfig(loaded)
      setConfigOffline(offline)
    })
  }, [])

  useEffect(() => {
    fetchDetections().then(setDetections).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    // A survivor-list failure does not blank the dashboard: the video, the
    // overlay and the per-frame detection count still work without it. The map
    // and the table say what is missing instead of rendering an empty field of
    // no pins and no rows, which would read as "no survivors found".
    fetchSurvivors().then(setSurvivors).catch((e) => setSurvivorsError(e.message))
  }, [])

  useEffect(() => {
    // Degrades like the survivor list rather than blanking anything: the log's
    // replay-start, acquisition and end-of-clip lines are derived from state
    // the dashboard already holds, so a failure here costs the cluster and
    // priority lines and the panel says which half is missing.
    fetchEvents().then(setEvents).catch((e) => setEventsError(e.message))
  }, [])

  // Unconditional: hooks cannot sit behind the early returns below. An empty
  // index is harmless because nothing renders against it until data arrives.
  const index = useMemo(() => buildDetectionIndex(detections ?? []), [detections])

  // ── The survivor roster ──────────────────────────────────────────
  // `survivorsFound` is the ONE list of survivors the drone has reached by the
  // current playback instant. The table renders it as rows and the header
  // renders its length, so the row count and the "survivors tracked" figure are
  // the same value and cannot drift — CLAUDE.md's requirement that counts
  // reconcile, satisfied by construction rather than by two calculations
  // agreeing. The map shades the same boundary: a survivor absent from this
  // list is the one drawn hollow.
  //
  // `first_frame <= currentFrame` is discovery, not localization. Every tracked
  // survivor has a position — the projection cannot fail — so a survivor
  // missing here is one the clip has not got to yet.
  //
  // null, not [], while the list is loading or has failed. An empty array would
  // make the header confidently display 0 survivors, which is a different claim
  // from "not known yet".
  const survivorsFound = useMemo(() => {
    if (survivors === null) return null
    return survivors.filter((s) => s.first_frame <= currentFrame)
  }, [survivors, currentFrame])

  // The clip's final frame, from the footage's true duration — NOT from the
  // last frame carrying a detection. Video usually runs on after the last
  // person leaves shot, and an end-of-clip line that fired at the last
  // detection would announce the end while the clip was visibly still playing.
  // Before metadata lands the detection extent is the only length available,
  // so it stands in, exactly as it does for the scrubber.
  const lastFrame =
    clipDuration > 0 && config
      ? Math.max(0, Math.round(clipDuration * config.clip_fps) - 1)
      : index.maxFrame

  const survivorsSoFar = survivorsFound?.length ?? null
  const survivorsInClip = survivors?.length ?? null

  const selectedSurvivor = useMemo(
    () => (survivors ?? []).find((s) => s.track_id === selectedTrackId) ?? null,
    [survivors, selectedTrackId],
  )

  // Shared by the map and the table. Clicking the already-selected pin or row
  // clears it, so both are their own deselect target and there is no state you
  // can only leave via the header.
  const handleSelectTrack = useCallback((trackId) => {
    setSelectedTrackId((current) => (current === trackId ? null : trackId))
  }, [])

  const clearSelection = useCallback(() => setSelectedTrackId(null), [])

  // `config` is the only hard requirement, and loadConfig never rejects — it
  // degrades to the bundled constants. So this gate is brief and cannot stick.
  //
  // It renders the LAYOUT rather than a centred spinner: the panels appear
  // where they will actually be, at the size they will actually be, so the
  // page does not jump when the data lands. On a projector a layout that
  // reflows once after load reads as a page that is still being built.
  if (!config || (!detections && !error)) {
    return <DashboardSkeleton />
  }

  // The operational block: exactly the space between the bottom of the header
  // and the fold. `100vh` is deliberate rather than `100dvh` — this is a
  // desktop dashboard on a projector, and a mobile URL bar that never appears
  // should not be budgeted for. Applied from `lg` up only; narrower than that
  // the two-column rows collapse to one and the page is allowed to scroll,
  // because four full-width panels cannot honestly fit in 720px anyway.
  const opsHeight = { '--ops-h': `calc(100vh - ${headerHeight}px)` }

  return (
    <div className="min-h-screen bg-surface-0 text-ink">
      <HeaderBar
        ref={measureHeader}
        config={config}
        configOffline={configOffline}
        frameDetectionCount={detectionsAt(index, currentFrame).length}
        survivorsSoFar={survivorsSoFar}
        survivorsInClip={survivorsInClip}
        selectedTrackId={selectedTrackId}
        selectedSurvivor={selectedSurvivor}
        onClearSelection={clearSelection}
      />

      <main>
        {/* ── Above the fold: everything that changes during playback ──
            Three rows in a fixed-height column, and every panel in them is
            whole and on screen at 1280×720. Nothing here is behind a click and
            nothing here is below the fold, because all four are things an
            operator MONITORS: the feed, the map, the queue and the log are four
            readings of the same playback instant, and a reading you have to
            scroll to is a reading you are not watching.

            The rows are `flex-[3]` and `flex-[2]`, not fixed pixel heights: the
            panels divide whatever the viewport actually gives them, so a taller
            screen makes the video and the map bigger rather than leaving a band
            of empty ground under the log. */}
        <div
          className="flex flex-col gap-3 px-4 pt-3 pb-3 lg:h-[var(--ops-h)]"
          style={opsHeight}
        >
          {/* A detections failure degrades the dashboard, it does not replace
              it. The clip is served from the frontend's own public/ directory,
              so the video still plays and the header still reports which
              constants are in force — which is the whole point of the offline
              badge beside it. An error page instead of a header is a dashboard
              that cannot tell you it is offline. It takes its space out of the
              panels below rather than pushing them past the fold. */}
          {error && (
            <div className="shrink-0 rounded-lg border border-hazard bg-surface-1 px-4 py-2.5">
              <p className="text-fine font-semibold text-ink">
                Detections unavailable — every count below reads 0
              </p>
              <p className="mt-0.5 text-eyebrow text-ink-soft">{error}</p>
              <p className="mt-0.5 text-eyebrow text-ink-muted">
                This is a failure to LOAD the detections file, not a scene with
                nothing in it. The clip still plays and the constants in the
                header are still the ones in force.
              </p>
            </div>
          )}

          {/* Row 2 — the two picture panels, side by side and roughly equal.
              They take the larger share because both are spatial: a map you
              cannot see the extent of and a video you cannot make out a person
              in are not worth the pixels they do get. `min-w-0` and `min-h-0`
              on the cells stop the Leaflet canvas and the video stage forcing
              the grid past the box they are supposed to fit inside. */}
          <div className="grid min-h-0 grid-cols-1 gap-3 lg:flex-[3] lg:grid-cols-2">
            <div className="min-h-0 min-w-0">
              <VideoPanel
                index={index}
                config={config}
                currentFrame={currentFrame}
                onFrameChange={setCurrentFrame}
                clipDuration={clipDuration}
                onDurationChange={setClipDuration}
                selectedTrackId={selectedTrackId}
              />
            </div>

            {/* The same two survivor figures the header is given and the same
                two the table is given — one derivation, three renderings. */}
            <div className="min-h-0 min-w-0">
              <MapPanel
                survivors={survivors}
                survivorsError={survivorsError}
                config={config}
                currentFrame={currentFrame}
                survivorsSoFar={survivorsSoFar}
                survivorsInClip={survivorsInClip}
                selectedTrackId={selectedTrackId}
                onSelectTrack={handleSelectTrack}
              />
            </div>
          </div>

          {/* Row 3 — the two list panels. Both are readings of the same instant
              as the row above: the queue is who has been found by this frame,
              the log is what happened up to it. Each scrolls inside its own box
              rather than growing the page, so the row's height is a budget the
              panels live within instead of a number they set. */}
          <div className="grid min-h-0 grid-cols-1 gap-3 lg:flex-[2] lg:grid-cols-2">
            {/* The rows are `survivorsFound`, whose length is the header's
                survivor count — the two cannot disagree because they are the
                same array. */}
            <div className="min-h-0 min-w-0">
              <SurvivorTable
                survivors={survivorsFound}
                survivorsInClip={survivorsInClip}
                survivorsError={survivorsError}
                config={config}
                selectedTrackId={selectedTrackId}
                onSelectTrack={handleSelectTrack}
              />
            </div>

            <div className="min-h-0 min-w-0">
              <EventLogPanel
                events={events}
                eventsError={eventsError}
                survivors={survivors}
                index={index}
                config={config}
                currentFrame={currentFrame}
                lastFrame={lastFrame}
                survivorsInClip={survivorsInClip}
              />
            </div>
          </div>
        </div>

        {/* ── Below the fold: reference material, and only reference material ──
            Neither of these changes while the clip plays. They are read once —
            by a judge asking where the numbers come from, or by an operator
            checking what the ramp means — and then never looked at again, which
            is exactly the wrong shape for something occupying the space four
            live panels need. Collapsed by default for the same reason: opening
            them is a deliberate act, and the closed summaries still name what
            is inside so nothing is hidden, only folded. */}
        <div className="flex flex-col gap-3 px-4 pb-8">
          <Reference
            title="Mission parameters — assumed"
            note={
              configOffline
                ? 'local constants · backend unreachable'
                : 'live from /api/config'
            }
            summary="Altitude, FOV, footprint, drone track, origin, threshold, on-device FPS — each tagged with where the number came from."
          >
            <MissionParameters config={config} configOffline={configOffline} />
          </Reference>

          <Reference
            title="Priority ramp and scoring"
            note="weights from /api/config"
            summary="What the four bands mean, where their cut points are, and the formula behind every score in the queue."
          >
            <PriorityReference config={config} />
          </Reference>
        </div>
      </main>
    </div>
  )
}

/**
 * A collapsed reference section.
 *
 * A plain `<details>`, deliberately — it is keyboard-operable, findable by the
 * browser's own find-in-page when open, and needs no state in App to track
 * whether it is showing. The one thing added over the bare element is that the
 * summary carries the section's title, its provenance note and a sentence
 * saying what is inside, so a closed section still tells a reader what they
 * would get by opening it. A disclosure whose closed state says only "details"
 * is a disclosure nobody opens.
 *
 * Nothing time-varying is ever allowed in here. The rule for this dashboard is
 * that a panel which changes during playback is neither below the fold nor
 * behind a click, and this component is the below-the-fold, behind-a-click
 * place — so its contents are, by construction, the things that hold still.
 */
function Reference({ title, note, summary, children }) {
  return (
    <details className="group rounded-lg border border-edge bg-surface-1">
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 marker:content-none [&::-webkit-details-marker]:hidden">
        {/* The chevron. Rotates rather than swapping glyphs, so the open and
            closed states are the same mark in two positions. */}
        <svg
          viewBox="0 0 12 12"
          aria-hidden="true"
          className="h-3 w-3 shrink-0 self-center fill-ink-muted transition-transform group-open:rotate-90"
        >
          <path d="M4 2l5 4-5 4z" />
        </svg>
        <span className="eyebrow">{title}</span>
        <span className="figure text-eyebrow text-ink-muted">{note}</span>
        <span className="min-w-0 flex-1 text-eyebrow text-ink-muted group-open:hidden">
          {summary}
        </span>
      </summary>

      <div className="border-t border-edge-soft px-4 py-4">{children}</div>
    </details>
  )
}

/**
 * The dashboard's shape, before it has anything to say.
 *
 * Deliberately built from the "not measured" tokens — a skeleton must not look
 * like a value. A grey block that could be mistaken for a reading of zero is
 * worse than no dashboard at all on a screen whose whole job is to be trusted.
 *
 * It is also silent about survivors. "0 survivors" and "not known yet" are
 * different claims and only one of them is true here.
 */
function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-surface-0 text-ink">
      <header className="border-b border-edge bg-surface-1">
        <div className="flex items-center gap-3 border-b border-edge-soft px-5 py-2.5">
          <span className="text-title leading-none font-bold tracking-tight text-ink">
            ARES
          </span>
          <span className="text-fine text-ink-muted">
            Adaptive Rescue and Exploration System
          </span>
        </div>
        <div className="flex flex-wrap">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex-1 border-l border-edge-soft px-5 py-3 first:border-l-0">
              <div className="skeleton h-2.5 w-24" />
              <div className="skeleton mt-2.5 h-8 w-16" />
              <div className="skeleton mt-2 h-2 w-32" />
            </div>
          ))}
        </div>
      </header>

      {/* The same three-row block the loaded dashboard uses, at the same
          proportions. The header here is a static copy of the real one, so its
          height is the same and `7.5rem` stands in for the measurement App has
          not taken yet — close enough that nothing jumps when the data lands,
          which is the whole point of drawing the layout rather than a spinner. */}
      <div className="flex flex-col gap-3 px-4 pt-3 pb-3 lg:h-[calc(100vh-7.5rem)]">
        <div className="grid min-h-0 grid-cols-1 gap-3 lg:flex-[3] lg:grid-cols-2">
          {[0, 1].map((i) => (
            <div key={i} className="flex min-h-0 min-w-0 flex-col">
              <div className="skeleton mb-2 h-2.5 w-28 shrink-0" />
              <div className="skeleton min-h-0 flex-1 rounded-lg" />
            </div>
          ))}
        </div>
        <div className="grid min-h-0 grid-cols-1 gap-3 lg:flex-[2] lg:grid-cols-2">
          {[0, 1].map((i) => (
            <div key={i} className="flex min-h-0 min-w-0 flex-col">
              <div className="skeleton mb-2 h-2.5 w-36 shrink-0" />
              <div className="skeleton min-h-0 flex-1 rounded-lg" />
            </div>
          ))}
        </div>
      </div>

      <p className="px-4 pb-8 text-fine text-ink-muted">Loading mission data…</p>
    </div>
  )
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchDetections, fetchSurvivors, loadConfig } from './api.js'
import { buildDetectionIndex, detectionsAt } from './detectionIndex.js'
import HeaderBar from './HeaderBar.jsx'
import MapPanel from './MapPanel.jsx'
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
  const [error, setError] = useState(null)
  const [currentFrame, setCurrentFrame] = useState(0)
  const [selectedTrackId, setSelectedTrackId] = useState(null)

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
  if (!config || (!detections && !error)) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
        <h1 className="text-2xl font-semibold">ARES</h1>
        <p className="mt-4 text-slate-400">Loading…</p>
      </main>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <HeaderBar
        config={config}
        configOffline={configOffline}
        frameDetectionCount={detectionsAt(index, currentFrame).length}
        survivorsSoFar={survivorsSoFar}
        survivorsInClip={survivorsInClip}
        selectedTrackId={selectedTrackId}
        selectedSurvivor={selectedSurvivor}
        onClearSelection={clearSelection}
      />

      <main className="p-8">
        {/* A detections failure degrades the dashboard, it does not replace it.
            The clip is served from the frontend's own public/ directory, so the
            video still plays and the header still reports which constants are in
            force — which is the whole point of the offline badge beside it. An
            error page instead of a header is a dashboard that cannot tell you
            it is offline. */}
        {error && (
          <div className="mb-6 max-w-[110rem] rounded-lg border border-red-900/60 bg-red-950/30 px-4 py-3">
            <p className="text-sm font-semibold text-red-300">
              Could not load detections — every count below reads 0
            </p>
            <p className="mt-0.5 text-xs text-slate-400">{error}</p>
          </div>
        )}

        <div className="grid max-w-[110rem] gap-8 lg:grid-cols-2">
          <VideoPanel
            index={index}
            config={config}
            currentFrame={currentFrame}
            onFrameChange={setCurrentFrame}
            selectedTrackId={selectedTrackId}
          />

          {/* The same two survivor figures the header is given and the same two
              the table is given — one derivation, three renderings. */}
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

          {/* Full width under both panels. The rows are `survivorsFound`, whose
              length is the header's survivor count — the two cannot disagree
              because they are the same array. */}
          <div className="lg:col-span-2">
            <SurvivorTable
              survivors={survivorsFound}
              survivorsInClip={survivorsInClip}
              survivorsError={survivorsError}
              config={config}
              selectedTrackId={selectedTrackId}
              onSelectTrack={handleSelectTrack}
            />
          </div>
        </div>
      </main>
    </div>
  )
}

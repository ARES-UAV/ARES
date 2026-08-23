import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchDetections, fetchSurvivors, loadConfig } from './api.js'
import { buildDetectionIndex, detectionsAt, uniqueTracksAt } from './detectionIndex.js'
import HeaderBar from './HeaderBar.jsx'
import MapPanel from './MapPanel.jsx'
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
 *   detections   — the whole clip's records, fetched once. Every count on the
 *                  dashboard is derived from this one array. CLAUDE.md requires
 *                  the counts to reconcile, which means one source of truth and
 *                  never a second independently-fetched total.
 *
 *   survivors    — one record per unique track_id with a lat/lon the backend
 *                  derived. This is a *view* of the same detections file, not a
 *                  second dataset: its length is `index.totalUniqueTracks` by
 *                  construction, which is why the map and the header agree.
 *
 *   currentFrame — the playback clock. VideoPanel derives it from the video's
 *                  currentTime and reports it up; the map, survivor table and
 *                  anything else time-varying read it from here, so the whole
 *                  dashboard is always showing the same instant.
 *
 *   selectedTrackId — which survivor the operator is looking at. Owned here
 *                  because it crosses panels: the map sets it, the video
 *                  overlay and the header render it.
 *
 * The derived index built from the detections is also owned here and passed
 * down. Panels are given numbers, not the raw array — a panel that counts for
 * itself is a panel that can disagree with the header.
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
    // overlay and every count still work without it. The map says what is
    // missing instead of rendering an empty field of no pins, which would read
    // as "no survivors found".
    fetchSurvivors().then(setSurvivors).catch((e) => setSurvivorsError(e.message))
  }, [])

  // Unconditional: hooks cannot sit behind the early returns below. An empty
  // index is harmless because nothing renders against it until data arrives.
  const index = useMemo(() => buildDetectionIndex(detections ?? []), [detections])

  const selectedSurvivor = useMemo(
    () => (survivors ?? []).find((s) => s.track_id === selectedTrackId) ?? null,
    [survivors, selectedTrackId],
  )

  // Clicking the already-selected marker clears it, so the map is its own
  // deselect target and there is no state you can only leave via the header.
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
        survivorsSoFar={uniqueTracksAt(index, currentFrame)}
        survivorsInClip={index.totalUniqueTracks}
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

          <MapPanel
            survivors={survivors}
            survivorsError={survivorsError}
            config={config}
            currentFrame={currentFrame}
            selectedTrackId={selectedTrackId}
            onSelectTrack={handleSelectTrack}
          />
        </div>
      </main>
    </div>
  )
}

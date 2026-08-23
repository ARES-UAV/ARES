import { useEffect, useState } from 'react'
import { fetchDetections } from './api.js'
import VideoPanel from './VideoPanel.jsx'

/**
 * ARES command dashboard.
 *
 * Two pieces of shared state live here and nowhere else:
 *
 *   detections   — the whole clip's records, fetched once. Every count on the
 *                  dashboard is derived from this one array. CLAUDE.md requires
 *                  the counts to reconcile, which means one source of truth and
 *                  never a second independently-fetched total.
 *
 *   currentFrame — the playback clock. VideoPanel derives it from the video's
 *                  currentTime and reports it up; the map, survivor table and
 *                  anything else time-varying read it from here, so the whole
 *                  dashboard is always showing the same instant.
 */
export default function App() {
  const [detections, setDetections] = useState(null)
  const [error, setError] = useState(null)
  const [currentFrame, setCurrentFrame] = useState(0)

  useEffect(() => {
    fetchDetections().then(setDetections).catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
        <h1 className="text-2xl font-semibold">ARES</h1>
        <p className="mt-4 text-red-400">Could not load detections</p>
        <p className="mt-1 text-sm text-slate-400">{error}</p>
      </main>
    )
  }

  if (!detections) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
        <h1 className="text-2xl font-semibold">ARES</h1>
        <p className="mt-4 text-slate-400">Loading…</p>
      </main>
    )
  }

  // -1 means the tracker did not assign an ID. Those detections are real, but
  // they cannot be de-duplicated, so they are excluded from the survivor count.
  const trackedIds = new Set(
    detections.filter((d) => d.track_id !== -1).map((d) => d.track_id),
  )

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <h1 className="text-2xl font-semibold">ARES</h1>

      <div className="mt-8 flex gap-12">
        <div>
          <div className="text-4xl font-semibold tabular-nums">
            {detections.length}
          </div>
          <div className="mt-1 text-sm text-slate-400">Total detections</div>
        </div>

        <div>
          <div className="text-4xl font-semibold tabular-nums">
            {trackedIds.size}
          </div>
          <div className="mt-1 text-sm text-slate-400">Survivors (unique tracks)</div>
        </div>
      </div>

      <div className="mt-8 max-w-4xl">
        <VideoPanel
          detections={detections}
          currentFrame={currentFrame}
          onFrameChange={setCurrentFrame}
        />
      </div>
    </main>
  )
}

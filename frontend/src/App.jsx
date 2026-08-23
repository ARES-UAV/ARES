import { useEffect, useMemo, useState } from 'react'
import { fetchDetections } from './api.js'
import { buildDetectionIndex, detectionsAt, uniqueTracksAt } from './detectionIndex.js'
import HeaderBar from './HeaderBar.jsx'
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
 *
 * The derived index built from those two is also owned here and passed down.
 * Panels are given numbers, not the raw array — a panel that counts for itself
 * is a panel that can disagree with the header.
 */
export default function App() {
  const [detections, setDetections] = useState(null)
  const [error, setError] = useState(null)
  const [currentFrame, setCurrentFrame] = useState(0)

  useEffect(() => {
    fetchDetections().then(setDetections).catch((e) => setError(e.message))
  }, [])

  // Unconditional: hooks cannot sit behind the early returns below. An empty
  // index is harmless because nothing renders against it until data arrives.
  const index = useMemo(() => buildDetectionIndex(detections ?? []), [detections])

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

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <HeaderBar
        frameDetectionCount={detectionsAt(index, currentFrame).length}
        survivorsSoFar={uniqueTracksAt(index, currentFrame)}
        survivorsInClip={index.totalUniqueTracks}
      />

      <main className="p-8">
        <div className="max-w-4xl">
          <VideoPanel
            index={index}
            currentFrame={currentFrame}
            onFrameChange={setCurrentFrame}
          />
        </div>
      </main>
    </div>
  )
}

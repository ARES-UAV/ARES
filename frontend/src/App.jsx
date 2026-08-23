import { useEffect, useState } from 'react'
import { fetchDetections } from './api.js'

/**
 * ARES command dashboard.
 *
 * Stage 0: prove one number travels from backend to browser. Deliberately
 * unstyled beyond the bare minimum — panels arrive in later stages.
 *
 * Both counts derive from the single `detections` array. CLAUDE.md requires
 * every count on the dashboard to reconcile, which means one shared source of
 * truth, never a second independently-fetched total.
 */
export default function App() {
  const [detections, setDetections] = useState(null)
  const [error, setError] = useState(null)

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
    </main>
  )
}

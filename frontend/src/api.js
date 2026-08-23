/**
 * Backend access for the dashboard.
 *
 * The base URL is configurable so the dashboard can point at something other
 * than the dev server later. CLAUDE.md also requires a path where the frontend
 * works with the backend switched off — that will load a static JSON file
 * through this same module, so keep fetching in here rather than in components.
 */
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function fetchDetections() {
  const res = await fetch(`${API_BASE}/api/detections`)
  if (!res.ok) {
    // The backend sends a useful "detail" string on 4xx/5xx — surface it
    // rather than a bare status code.
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch {
      // Response wasn't JSON; the status code is all we have.
    }
    throw new Error(detail)
  }
  return res.json()
}

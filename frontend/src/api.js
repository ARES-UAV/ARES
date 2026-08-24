/**
 * Backend access for the dashboard.
 *
 * The base URL is configurable so the dashboard can point at something other
 * than the dev server later. It lives in `config.js` rather than here because
 * the map's tile URL is built from it too — the backend serves the cached
 * OpenStreetMap tiles — and those two must not be able to drift apart.
 *
 * CLAUDE.md also requires a path where the frontend works with the backend
 * switched off — that will load a static JSON file through this same module,
 * so keep fetching in here rather than in components.
 */
import { API_BASE, FALLBACK_CONFIG } from './config.js'

/**
 * Fetch JSON from an API path, turning the backend's error `detail` into the
 * thrown message.
 *
 * @param {string} path
 * @returns {Promise<any>}
 */
async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`)
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

export function fetchDetections() {
  return getJson('/api/detections')
}

/**
 * The clip's mission event timeline.
 *
 * Only the half of the log that needs server-side maths: cluster formation and
 * priority bands. The other half — replay start, first detections, the closing
 * summary — is derived in `missionLog.js` from the survivor roster the
 * dashboard already holds, so the log's acquisition lines and the header's
 * survivor count are one list rather than two that must agree.
 *
 * A failure here degrades the log rather than removing it, and the panel says
 * which half is missing.
 */
export function fetchEvents() {
  return getJson('/api/events')
}

export function fetchSurvivors() {
  return getJson('/api/survivors')
}

/**
 * Load the clip and camera constants, falling back to the bundled copy.
 *
 * This one never throws. Every other panel can show an error state, but the
 * numbers in `config` are what the video overlay and the map are *drawn with* —
 * with nothing to draw against there is no dashboard at all. So a failure here
 * degrades to the values in `config.js` and reports that it did, and the header
 * shows an offline badge. That is the honest version: the dashboard keeps
 * working, and it says out loud that the figures are local rather than live.
 *
 * @returns {Promise<{config: object, offline: boolean, reason: string|null}>}
 */
export async function loadConfig() {
  try {
    const config = await getJson('/api/config')
    return { config, offline: false, reason: null }
  } catch (e) {
    return { config: FALLBACK_CONFIG, offline: true, reason: e.message }
  }
}

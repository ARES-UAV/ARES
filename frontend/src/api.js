/**
 * Backend access for the dashboard.
 *
 * The base URL is configurable so the dashboard can point at something other
 * than the dev server later. It lives in `config.js` rather than here because
 * the map's tile URL is built from it too — the backend serves the cached
 * OpenStreetMap tiles — and those two must not be able to drift apart.
 *
 * CONVENTIONS.md also requires a path where the frontend works with the backend
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
 * priority bands. The other half — replay start, survivor confirmations, the
 * closing summary — is derived in `missionLog.js` from the survivor roster the
 * dashboard already holds, so the log's confirmation lines and the header's
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

/**
 * Ground routes from the rescue staging point to each confirmed survivor.
 *
 * Supplementary, not load-bearing: a failure here costs the route overlay and
 * nothing else, so the map still plots every survivor and the queue still
 * ranks them. The panel says the routes are missing rather than going quiet.
 */
export function fetchRoutes() {
  return getJson('/api/routes')
}

/**
 * The alert queue — what warranted interrupting somebody, and whether it got
 * through.
 *
 * Degrades like the routes: a failure costs the alert strip and nothing else.
 * The map, the queue and the log are unaffected, and the strip says the queue
 * is unreadable rather than rendering an empty one — "no alerts" and "cannot
 * tell" are different claims and only one of them would be true.
 */
export function fetchAlerts() {
  return getJson('/api/alerts')
}

/**
 * Attempt delivery of every alert not already sent.
 *
 * A POST, and the only call in this module that changes anything on the
 * server: it writes to the delivery ledger. It is deliberately operator-
 * driven rather than automatic — a dashboard that fires webhooks on page load
 * would transmit every time a judge refreshed it.
 *
 * Resolves with a FlushResult even when nothing was attempted; `channel: null`
 * means none is configured, which is not an error.
 */
export async function flushAlerts() {
  const res = await fetch(`${API_BASE}/api/alerts/flush`, { method: 'POST' })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch {
      // Not JSON; the status code is all we have.
    }
    throw new Error(detail)
  }
  return res.json()
}

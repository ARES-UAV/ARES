import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  COLORS,
  MAP_DEFAULT_ZOOM,
  MAP_FIT_MAX_ZOOM,
  MAP_MAX_NATIVE_ZOOM,
  MAP_MAX_ZOOM,
  TILE_ATTRIBUTION,
  TILE_URL,
} from './config.js'

/**
 * Survivor positions on an OpenStreetMap base layer.
 *
 * Leaflet is driven imperatively rather than through a React wrapper. It owns
 * its own DOM subtree and its own event loop, and one more dependency between
 * here and the map is one more thing that can break on 5 September — the video
 * overlay next door is imperative for the same reason.
 *
 * Markers are circles, not Leaflet's default pin. That is partly the palette
 * (a circle takes an arbitrary fill; the default pin is a fixed blue PNG whose
 * asset path is a known bundler trap) and partly meaning: a pin points at a
 * surveyed point, and these positions are a flat-earth estimate from a fixed
 * assumed altitude. A soft circle reads as "about here", which is the truth.
 *
 * The panel counts nothing for itself. `survivorsSoFar` and `survivorsInClip`
 * are the same two numbers App hands the header and the survivor table — the
 * length of the roster the table renders as rows — so the figure here, the
 * header's survivor count and the table's row count are one value rendered
 * three times rather than three calculations that happen to agree.
 *
 * They are counts of DISCOVERY, not of localization success. Every tracked
 * survivor gets a position — `bbox_to_latlon` cannot fail — so a survivor
 * missing from the count has not been reached by the playback clock yet, and
 * is drawn hollow rather than hidden. The wording has to carry that: "6 of 9
 * located" read as "localization worked for 6 of them", which is a bug report
 * about a system that is working correctly.
 */

/** Radius in px for a survivor circle, selected or not. */
const MARKER_RADIUS = 7
const MARKER_RADIUS_SELECTED = 11

/**
 * Attach the `#id` label to a marker.
 *
 * Unselected markers label on hover only: the whole survivor field spans a
 * couple of dozen metres, so nine always-on labels overlap into an unreadable
 * stack. The selected one is permanent, because the point of selecting is to
 * keep track of that survivor while looking somewhere else.
 *
 * Permanence is fixed when a Leaflet tooltip is bound, so switching it means
 * rebinding. Both call sites go through here so the label cannot change shape
 * depending on which one last touched it.
 */
function bindTrackTooltip(marker, trackId, selected) {
  marker.unbindTooltip()
  marker.bindTooltip(`#${trackId}`, {
    permanent: selected,
    direction: 'right',
    offset: [10, 0],
    className: 'ares-track-tooltip',
  })
}

export default function MapPanel({
  survivors,
  survivorsError,
  config,
  currentFrame,
  survivorsSoFar,
  survivorsInClip,
  selectedTrackId,
  onSelectTrack,
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef(new Map())
  const fittedRef = useRef(false)

  // Tiles need internet and venue wifi fails (CLAUDE.md, demo-day constraint
  // 3). A tile server that cannot be reached otherwise renders as a silent
  // grey rectangle, which looks like a broken dashboard rather than a missing
  // network — so say which it is.
  const [tilesFailed, setTilesFailed] = useState(false)

  // Kept in a ref so the map-creation effect below never re-runs — and so does
  // not destroy and rebuild the whole map — just because App handed down a new
  // callback identity on re-render.
  const onSelectTrackRef = useRef(onSelectTrack)
  useEffect(() => {
    onSelectTrackRef.current = onSelectTrack
  })

  // Read when a marker is first created, to give it the right label shape
  // immediately. The effects below own every later change, so this is not a
  // dependency of the marker-sync effect — it would only make it re-run.
  const selectedTrackIdRef = useRef(selectedTrackId)
  useEffect(() => {
    selectedTrackIdRef.current = selectedTrackId
  })

  // ── Create the map once ──────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Captured now rather than read in the cleanup: the cleanup runs after the
    // component may already have moved on, and the marker table it has to empty
    // is the one this map's markers were added to.
    const markers = markersRef.current

    const map = L.map(container, {
      center: [config.origin_lat, config.origin_lon],
      zoom: MAP_DEFAULT_ZOOM,
      maxZoom: MAP_MAX_ZOOM,
      // The scale bar earns its place here: the clip covers a couple of dozen
      // metres, and without it a viewer has no way to tell whether the pins
      // are metres or kilometres apart.
      attributionControl: true,
    })

    L.control.scale({ imperial: false }).addTo(map)

    const tiles = L.tileLayer(TILE_URL, {
      maxNativeZoom: MAP_MAX_NATIVE_ZOOM,
      maxZoom: MAP_MAX_ZOOM,
      attribution: TILE_ATTRIBUTION,
    })

    let anyTileLoaded = false
    tiles.on('tileload', () => {
      anyTileLoaded = true
      setTilesFailed(false)
    })
    // A single failed tile at the edge of the viewport is normal. Nothing
    // loading at all is not — that is the offline case worth reporting.
    tiles.on('tileerror', () => {
      if (!anyTileLoaded) setTilesFailed(true)
    })

    tiles.addTo(map)

    // Leaflet measures its container on creation. Inside a flex/grid layout
    // that measurement can land before the panel has its final width, leaving
    // the map rendered into a strip of its box.
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(container)

    mapRef.current = map
    return () => {
      observer.disconnect()
      map.remove()
      mapRef.current = null
      markers.clear()
      fittedRef.current = false
    }
  }, [config.origin_lat, config.origin_lon])

  // ── Sync markers to the survivor list ────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const markers = markersRef.current
    const live = new Set()

    for (const survivor of survivors ?? []) {
      live.add(survivor.track_id)
      let marker = markers.get(survivor.track_id)

      if (!marker) {
        marker = L.circleMarker([survivor.latitude, survivor.longitude], {
          radius: MARKER_RADIUS,
          color: COLORS.survivor,
          fillColor: COLORS.survivor,
        })
        marker.on('click', () => onSelectTrackRef.current(survivor.track_id))
        bindTrackTooltip(
          marker,
          survivor.track_id,
          survivor.track_id === selectedTrackIdRef.current,
        )
        marker.addTo(map)
        markers.set(survivor.track_id, marker)
      } else {
        marker.setLatLng([survivor.latitude, survivor.longitude])
      }
    }

    for (const [trackId, marker] of markers) {
      if (!live.has(trackId)) {
        marker.remove()
        markers.delete(trackId)
      }
    }

    // Frame the survivors once, on the first list that has any. Re-fitting on
    // every update would yank the view out from under someone who has panned
    // or zoomed to look at a specific pin.
    if (!fittedRef.current && markers.size > 0) {
      const bounds = L.latLngBounds(
        (survivors ?? []).map((s) => [s.latitude, s.longitude]),
      )
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: MAP_FIT_MAX_ZOOM })
      fittedRef.current = true
    }
  }, [survivors])

  // ── Restyle for selection and for discovery ──────────────────────
  // Two independent things are shown by style rather than by adding or removing
  // pins: which survivor is selected, and which have been found by the current
  // playback instant. A survivor the drone has not reached yet is drawn hollow
  // instead of hidden — removing the pin would make the panel's count and the
  // header's disagree with what is on screen, and would also make the map jump
  // as pins appeared.
  useEffect(() => {
    for (const survivor of survivors ?? []) {
      const marker = markersRef.current.get(survivor.track_id)
      if (!marker) continue

      const discovered = survivor.first_frame <= currentFrame
      const selected = survivor.track_id === selectedTrackId

      marker.setStyle({
        radius: selected ? MARKER_RADIUS_SELECTED : MARKER_RADIUS,
        weight: selected ? 3 : 2,
        opacity: discovered ? 1 : 0.5,
        color: selected ? '#ffffff' : COLORS.survivor,
        fillColor: COLORS.survivor,
        fillOpacity: discovered ? 0.85 : 0.15,
      })
      if (selected) marker.bringToFront()
    }
  }, [survivors, selectedTrackId, currentFrame])

  // ── Pin the selected marker's label ──────────────────────────────
  // Separate from the restyle above because it must NOT run on every frame.
  // Rebinding a tooltip 24 times a second makes it flicker, and selection is
  // the only thing that changes which label is pinned.
  useEffect(() => {
    for (const [trackId, marker] of markersRef.current) {
      const selected = trackId === selectedTrackId
      const tooltip = marker.getTooltip()
      if (tooltip && Boolean(tooltip.options.permanent) === selected) continue
      bindTrackTooltip(marker, trackId, selected)
    }
  }, [survivors, selectedTrackId])

  return (
    <section className="flex flex-col">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Survivor map
        </h2>
        {/* Deliberately NOT "N of M located". Every tracked survivor has a
            position; this is how many the clip has reached by the current
            frame, which is the header's "survivors tracked" figure and the
            same prop. "Located" invited the reading that localization had
            failed for the rest. */}
        <span className="text-[11px] tabular-nums text-slate-500">
          {survivorsError
            ? 'positions unavailable'
            : survivorsSoFar === null
              ? 'loading positions…'
              : `${survivorsSoFar} of ${survivorsInClip} found by this frame`}
        </span>
      </div>

      {/* Its own row, above the map, not an overlay on it. Leaflet puts the
          zoom control at the top-left of the map pane and gives it a z-index
          this banner would have to fight; a banner stacked under a "+" button
          hides the very word that says what is wrong. Taking a row costs a
          line of vertical space only when the tiles have actually failed. */}
      {tilesFailed && (
        <div className="mb-2 rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-[11px] leading-relaxed text-amber-300">
          Map tiles unreachable — survivor positions are still plotted, the base
          map is not.
        </div>
      )}

      <div className="relative isolate overflow-hidden rounded-lg border border-slate-800">
        <div ref={containerRef} className="h-[24rem] w-full bg-slate-900" />

        {survivorsError && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-slate-950/85 px-6 text-center text-sm text-slate-400">
            Could not load survivor positions — {survivorsError}
          </div>
        )}
      </div>

      {/* The assumption behind every pin, stated on the panel rather than
          buried in the pitch. A judge asking "how do you know where they are?"
          should be able to read the answer off the screen. */}
      <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
        Positions derived from pixel offset at a fixed{' '}
        <span className="tabular-nums text-slate-400">{config.altitude_m} m</span> altitude
        and{' '}
        <span className="tabular-nums text-slate-400">{config.camera_fov_deg}°</span> FOV
        over flat terrain, along an assumed constant-velocity track of{' '}
        <span className="tabular-nums text-slate-400">{config.drone_speed_ms} m/s</span>{' '}
        on heading{' '}
        <span className="tabular-nums text-slate-400">{config.drone_heading_deg}°</span>.
        No live telemetry — altitude, FOV and that track are per-clip constants.
        Hollow markers are survivors the clip has not reached yet — they are
        exactly the ones with no row in the priority queue below. Click a marker
        or a table row to highlight that track in all three panels.
      </p>
    </section>
  )
}

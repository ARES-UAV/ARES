import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
// Leaflet's own stylesheet is imported in main.jsx, NOT here. It has to load
// before index.css or its light-theme defaults win the cascade on equal
// specificity and the zoom buttons and scale bar stay white on a dark
// dashboard. Import order is the only thing deciding that, so it lives in the
// one file that states the order deliberately.
import {
  MAP_DEFAULT_ZOOM,
  MAP_FIT_MAX_ZOOM,
  MAP_MAX_NATIVE_ZOOM,
  MAP_MAX_ZOOM,
  TILE_ATTRIBUTION,
  TILE_URL,
} from './config.js'
import { token, SURVIVOR, SELECTION_HALO } from './theme.js'

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
 * They are counts of CONFIRMATION, not of localization success. Every tracked
 * survivor gets a position — `bbox_to_latlon` cannot fail — so a survivor
 * missing from the count has not cleared the persistence threshold by the
 * current playback instant, and is drawn hollow rather than hidden. The
 * wording has to carry that: "6 of 9 located" read as "localization worked for
 * 6 of them", which is a bug report about a system that is working correctly.
 *
 * Every pin on this map is a confirmed survivor. The tracks the filter dropped
 * are not plotted at all and are not drawn hollow either — hollow means "not
 * yet", and a two-frame flicker is never going to become a person. They remain
 * visible where they belong: as boxes on the video overlay, which draws the
 * raw detections file unfiltered.
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

  // Tiles come from the backend's bundled cache, not the internet (CLAUDE.md,
  // demo-day constraint 3 — venue wifi fails). Missing tiles otherwise render
  // as a silent grey rectangle, which looks like a broken dashboard rather
  // than a base map that has run out — so say which it is.
  const [tilesMissing, setTilesMissing] = useState(false)

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
      // Off, deliberately, and this is a demo-day decision rather than a
      // preference. The dashboard is taller than a 1280x-something projector,
      // so the page scrolls — and a Leaflet map swallows the wheel events that
      // would have scrolled it, zooming instead. Measured: one wheel tick with
      // the cursor over the panel moves the map a full zoom level, and a few
      // ticks put the survivors off-screen entirely. On stage that is someone
      // scrolling down to the priority queue and arriving at an empty map they
      // now have to fix in front of judges.
      //
      // The +/- control and drag-to-pan are untouched, so nothing is actually
      // lost: zooming is still available, it just cannot happen by accident.
      scrollWheelZoom: false,
    })

    L.control.scale({ imperial: false }).addTo(map)

    const tiles = L.tileLayer(TILE_URL, {
      maxNativeZoom: MAP_MAX_NATIVE_ZOOM,
      maxZoom: MAP_MAX_ZOOM,
      attribution: TILE_ATTRIBUTION,
    })

    // Reported per VIEW, not latched for the session. The tiles are a bundled
    // box now, so a gap is no longer only the offline case it used to be —
    // panning or zooming past the edge of the bundle is the ordinary way to
    // find one, and it must be recoverable: pan back inside and the banner has
    // to go away again. So the count resets when Leaflet starts loading a
    // view and is judged when it finishes.
    //
    // `load` fires once the visible tiles are settled, errors included, which
    // is why this does not flicker on every individual 404 during a pan.
    let errorsThisView = 0
    tiles.on('loading', () => {
      errorsThisView = 0
    })
    tiles.on('tileerror', () => {
      errorsThisView += 1
    })
    tiles.on('load', () => setTilesMissing(errorsThisView > 0))

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
        // Leaflet writes these as SVG presentation attributes, which do not
        // resolve `var()` — so the token is read for its computed value here
        // rather than referenced. tokens.css is still the only place it is
        // written down. See theme.js.
        const survivorColor = token(SURVIVOR)
        marker = L.circleMarker([survivor.latitude, survivor.longitude], {
          radius: MARKER_RADIUS,
          color: survivorColor,
          fillColor: survivorColor,
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
  // pins: which survivor is selected, and which have been confirmed by the
  // current playback instant. A survivor not yet confirmed is drawn hollow
  // instead of hidden — removing the pin would make the panel's count and the
  // header's disagree with what is on screen, and would also make the map jump
  // as pins appeared.
  useEffect(() => {
    const survivorColor = token(SURVIVOR)
    const haloColor = token(SELECTION_HALO)

    for (const survivor of survivors ?? []) {
      const marker = markersRef.current.get(survivor.track_id)
      if (!marker) continue

      // Confirmation, not first sighting — the same boundary the header's
      // survivor figure and the table's rows use. Shading on `first_frame`
      // would fill a pin in 2.5 seconds before the count acknowledged it.
      const discovered = survivor.confirmed_frame <= currentFrame
      const selected = survivor.track_id === selectedTrackId

      marker.setStyle({
        radius: selected ? MARKER_RADIUS_SELECTED : MARKER_RADIUS,
        weight: selected ? 3 : 2,
        opacity: discovered ? 1 : 0.5,
        // The selected pin is ringed in ink, not in a ramp colour: those mean
        // rank, and a pin that turned orange when it was clicked would read as
        // a change in priority. Not cyan either — a cyan ring around a cyan
        // circle carries nothing.
        color: selected ? haloColor : survivorColor,
        fillColor: survivorColor,
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
    <section className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex shrink-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="eyebrow">Survivor map</h2>
        {/* Deliberately NOT "N of M located". Every tracked survivor has a
            position; this is how many the clip has confirmed by the current
            frame, which is the header's "confirmed survivors" figure and the
            same prop. "Located" invited the reading that localization had
            failed for the rest. */}
        <span className="figure text-eyebrow text-ink-muted">
          {survivorsError
            ? 'positions unavailable'
            : survivorsSoFar === null
              ? 'loading positions…'
              : `${survivorsSoFar} of ${survivorsInClip} confirmed by this frame`}
        </span>
      </div>

      {/* Its own row, above the map, not an overlay on it. Leaflet puts the
          zoom control at the top-left of the map pane and gives it a z-index
          this banner would have to fight; a banner stacked under a "+" button
          hides the very word that says what is wrong. Taking a row costs a
          line of vertical space only when the tiles have actually failed. */}
      {tilesMissing && (
        <div className="mb-2 shrink-0 rounded-md border border-edge bg-surface-2 px-3 py-2 text-eyebrow leading-relaxed text-ink-soft">
          Map tiles unavailable for this view — survivor positions are still
          plotted, the base map is not. Tiles are cached on disk for the search
          area only; positions do not come from the tile server.
        </div>
      )}

      {/* The map takes whatever height the row has left rather than a fixed
          24rem: the four operational panels have to fit above the fold at
          1280×720, so the row's height is the budget and the map is sized from
          it. Leaflet is already watched by a ResizeObserver that calls
          invalidateSize, so it re-tiles correctly at any size this produces. */}
      <div className="relative isolate min-h-0 flex-1 overflow-hidden rounded-lg border border-edge">
        <div ref={containerRef} className="h-full w-full bg-surface-1" />

        {/* Loading. The base map is already drawn underneath — this covers only
            the claim about survivors, because an empty map with no pins and no
            message reads as "no survivors found", which is a different and
            much worse statement than "not known yet". */}
        {survivors === null && !survivorsError && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 bg-surface-1/90 px-6 text-center">
            <div className="skeleton h-2 w-40" />
            <p className="text-fine text-ink-muted">Loading survivor positions…</p>
          </div>
        )}

        {survivorsError && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-2 bg-surface-1/95 px-6 text-center">
            <p className="text-body font-semibold text-ink">Positions unavailable</p>
            <p className="text-fine text-ink-soft">{survivorsError}</p>
            <p className="text-eyebrow text-ink-muted">
              The clip and its detection overlay are unaffected.
            </p>
          </div>
        )}
      </div>

      {/* The assumption behind every pin, stated on the panel rather than
          buried in the pitch. A judge asking "how do you know where they are?"
          should be able to read the answer off the screen. */}
      <p className="mt-2 shrink-0 text-eyebrow leading-relaxed text-ink-muted">
        Positions derived from pixel offset at a fixed{' '}
        <span className="figure text-ink-soft">{config.altitude_m} m</span> altitude
        and{' '}
        <span className="figure text-ink-soft">{config.camera_fov_deg}°</span> FOV
        over flat terrain, along an assumed constant-velocity track of{' '}
        <span className="figure text-ink-soft">{config.drone_speed_ms} m/s</span>{' '}
        on heading{' '}
        <span className="figure text-ink-soft">{config.drone_heading_deg}°</span>.
        Per-clip constants, not live telemetry. Hollow markers are survivors the
        clip has not reached yet — exactly the ones with no row in the priority
        queue. Click a marker or a row to highlight that track in all three panels.
      </p>

      {/* Group annotation. Groups are connected components within the same
          CLUSTER_RADIUS_M, so they are a map-side summary of the table's
          `group_id`/`group_size` and the event log's cluster lines — one
          geometry, three readings. On the demo clip every confirmed survivor
          lands inside one 11 m patch, so this reads "one group of 23", which
          is exactly why the cluster scoring term was dropped rather than
          scored: a term identical in every row cannot rank them. */}
      <p className="mt-1.5 shrink-0 text-eyebrow leading-relaxed text-ink-muted">
        {survivors !== null && survivors.length > 0 ? (
          <>
            <span className="figure text-ink-soft">
              {new Set((survivors ?? []).map((s) => s.group_id)).size}
            </span>{' '}
            connected group
            {new Set((survivors ?? []).map((s) => s.group_id)).size === 1 ? ' ' : 's '}
            within{' '}
            <span className="figure text-ink-soft">{config.cluster_radius_m} m</span>{' '}
            of one another (largest holds{' '}
            <span className="figure text-ink-soft">
              {Math.max(0, ...(survivors ?? []).map((s) => s.group_size))}
            </span>{' '}
            survivors).
          </>
        ) : (
          'Grouping awaits the first confirmed survivor.'
        )}
      </p>
    </section>
  )
}

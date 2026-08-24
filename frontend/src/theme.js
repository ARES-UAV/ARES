/**
 * Resolved token values, for the two places that cannot use a CSS variable.
 *
 * Almost everything on this dashboard takes colour from a class or an inline
 * `var(--token)` and never needs this. Two things cannot:
 *
 *   the video overlay — a canvas 2D context takes `strokeStyle` as a colour
 *                       string. It is not CSS and `var(--survivor)` means
 *                       nothing to it.
 *
 *   Leaflet markers   — circle styles are written as SVG presentation
 *                       attributes, and `var()` is not resolved in an
 *                       attribute value in any browser we would demo on.
 *
 * So they read the computed value off `:root` instead of holding a literal.
 * That keeps tokens.css the single place a colour is written down: change a
 * token and the bounding boxes and the map pins follow, with nothing here to
 * update.
 *
 * Values are cached because tokens.css is static — there is no theme switch on
 * this dashboard, so a token cannot change after first paint. An EMPTY result
 * is deliberately not cached: it means the stylesheet had not applied yet, and
 * the next call should try again rather than remember the miss forever.
 */

const resolved = new Map()

/**
 * The computed value of a CSS custom property on the document root.
 *
 * @param {string} name token name including the leading `--`
 * @returns {string} the colour string, or '' before styles have applied
 */
export function token(name) {
  const hit = resolved.get(name)
  if (hit) return hit

  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()

  if (value) resolved.set(name, value)
  return value
}

/** Survivor detections: bounding boxes and map pins. Never text. */
export const SURVIVOR = '--survivor'

/**
 * Label text sitting ON a survivor-cyan chip, and the ring around a map
 * marker. The page ground, used as ink — dark on cyan, which is the only
 * legible direction for that pair.
 */
export const ON_SURVIVOR = '--surface-0'

/**
 * The halo under a selected bounding box and around a selected map pin.
 *
 * Not white. The token file's own note applies — full white on near-black
 * glares on a projector — and `--ink` is the value that was chosen instead.
 * It also cannot be survivor cyan: a cyan halo around a cyan box carries no
 * information at all.
 */
export const SELECTION_HALO = '--ink'

import { useId, useState } from 'react'

/**
 * The frame every operational panel sits in.
 *
 * Three jobs, and the third is the reason it exists.
 *
 * ── 1. One header, not five ──────────────────────────────────────────
 * Each panel used to spell its own header out of the same four utility
 * classes. That is how a dashboard drifts: five headers that are 95% alike
 * look like five decisions rather than one, and nobody notices the odd one
 * out until it is on a projector.
 *
 * ── 2. Prose goes behind a disclosure ────────────────────────────────
 * These panels carry a lot of explanation, and the explanation is load-bearing
 * — it is what lets a judge ask "how do you know where they are?" and read the
 * answer off the screen instead of taking it on trust. But it was set below
 * each panel as three stacked paragraphs of 11px type, which cost the map
 * roughly a fifth of its height and made the page look like documentation with
 * a dashboard embedded in it.
 *
 * So the prose moves in here, behind an "info" toggle in the header. Nothing
 * is deleted and nothing is hidden — the toggle is always visible, it is
 * keyboard-operable, and the panel is a live region either way. The rule for
 * what belongs behind it is sharp:
 *
 *   BEHIND THE TOGGLE   things that do not change while the clip plays:
 *                       assumptions, provenance, what a colour means, what
 *                       the panel is NOT.
 *
 *   ALWAYS VISIBLE      anything that changes with the playback clock or the
 *                       selection, and every error state.
 *
 * An error never folds. A panel that hid the sentence explaining why it is
 * empty would be worse than one with no explanation at all.
 *
 * ── 3. It owns the flex contract ─────────────────────────────────────
 * `min-h-0` on a flex child is the difference between a panel that fits its
 * budget and one that shoves the row past the fold. Getting it right once here
 * is better than getting it right five times.
 */
export default function PanelShell({
  title,
  meta,
  note,
  status,
  tone = null,
  children,
}) {
  const [showNote, setShowNote] = useState(false)
  const noteId = useId()

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex shrink-0 flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="eyebrow">{title}</h2>

        {/* Live figures sit with the title, where a reading belongs. */}
        {meta != null && (
          <span className="figure text-eyebrow text-ink-muted">{meta}</span>
        )}

        <span className="flex-1" />

        {note != null && (
          <button
            type="button"
            onClick={() => setShowNote((v) => !v)}
            aria-expanded={showNote}
            aria-controls={noteId}
            title={
              showNote
                ? 'Hide the assumptions behind this panel'
                : 'What this panel assumes, and what it is not'
            }
            className={`flex h-[18px] shrink-0 items-center gap-1 rounded border px-1.5 text-eyebrow font-semibold tracking-wider uppercase transition-colors ${
              showNote
                ? 'border-ink-muted bg-surface-2 text-ink'
                : 'border-edge text-ink-muted hover:border-ink-muted hover:text-ink-soft'
            }`}
          >
            {/* A glyph AND the word. An `i` in a circle on its own is a
                convention, and a convention is exactly what a judge who has
                never seen this screen before does not have. */}
            <span aria-hidden="true" className="figure leading-none">
              ⓘ
            </span>
            Basis
          </button>
        )}
      </div>

      {/* The panel's own box. `min-h-0` is what keeps it inside its row, and
          `relative` is what lets the note sit OVER it. */}
      <div
        className={`relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border bg-surface-1 ${
          tone === 'hazard' ? 'border-hazard' : 'border-edge'
        }`}
      >
        {children}

        {/* The disclosure COVERS the panel; it does not push it down.
            Measured: displacing the body crushed the map to a 20px strip with
            the pins sitting on the attribution line, which looks like a broken
            panel rather than an open explanation. The rows above the fold are
            a fixed height budget, so anything inserted into one has to come
            out of the thing you are trying to explain.

            Overlaying is also the truer model. This is not a second section of
            the panel — it is the panel's own footnotes, held up in front of
            it, and dismissed with the same button that raised them. The body
            stays mounted underneath, so Leaflet is never resized, the video
            never re-seeks, and the log keeps its scroll position. */}
        {note != null && showNote && (
          <div
            id={noteId}
            className="absolute inset-0 z-20 overflow-y-auto bg-surface-1/97 px-3 py-2.5 text-eyebrow leading-relaxed text-ink-soft backdrop-blur-[2px]"
          >
            {note}
          </div>
        )}
      </div>

      {/* One line, always visible, never folded: whatever is true right now. */}
      {status != null && (
        <p className="mt-1.5 shrink-0 truncate text-eyebrow text-ink-muted">
          {status}
        </p>
      )}
    </section>
  )
}

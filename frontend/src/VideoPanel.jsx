import { useCallback, useEffect, useRef, useState } from 'react'
import { timecode } from './clock.js'
import { detectionsAt } from './detectionIndex.js'
import { CLIP_SRC } from './config.js'
import { token, SURVIVOR, ON_SURVIVOR, SELECTION_HALO } from './theme.js'

/**
 * The demo clip with its detection overlay, and the playback controls.
 *
 * Two stacked layers at identical size: a <video> and a transparent <canvas>.
 *
 * This component does not own the playback clock — it reports the current
 * frame upward via `onFrameChange` and renders whatever `currentFrame` it is
 * given back. Other panels (map, survivor table) read the same value from App,
 * which is what keeps every count on the dashboard reconciled.
 *
 * It does not own the detection index either. The header's "raw detections this
 * frame" and the boxes drawn here are the same lookup into the same map, so
 * they cannot report different numbers for the same instant.
 *
 * Nor does it own the clip geometry: fps and the source resolution arrive in
 * `config`, which comes from the backend when it is reachable. Hard-coding them
 * here is how the overlay ends up drawn against the wrong frame after someone
 * changes the clip and updates only one of the two places that knew its rate.
 *
 * ── Why the controls are custom ──────────────────────────────────────
 * The native <video controls> bar is a different shape, colour and type on
 * every browser, sits over the bottom of the overlay, and — the reason that
 * actually matters — has no concept of a frame. The demo is a frame-indexed
 * replay: a judge asking "go back to the one at frame 300" needs a frame
 * number to scrub against, not a timecode to estimate from. So the scrubber is
 * denominated in FRAMES and the video's currentTime is derived from it, which
 * is the same direction the rest of the dashboard reasons in.
 */

/** Frames stepped by the step-back / step-forward buttons. */
const STEP_FRAMES = 1

/** A control-bar button. */
function ControlButton({ onClick, disabled, label, wide = false, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`flex h-8 items-center justify-center rounded border border-edge bg-surface-2 text-ink-soft transition-colors hover:border-ink-muted hover:text-ink disabled:cursor-default disabled:border-edge-soft disabled:text-ink-muted ${
        wide ? 'w-12' : 'w-8'
      }`}
    >
      {children}
    </button>
  )
}

export default function VideoPanel({
  index,
  config,
  currentFrame,
  onFrameChange,
  clipDuration,
  onDurationChange,
  selectedTrackId,
}) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const frameRef = useRef(null)

  // The PICTURE's CSS size — not the frame's. The frame is whatever width the
  // column has and whatever height the row has left over; the picture is the
  // source aspect ratio contained inside it. Bounding boxes are scaled from the
  // source coordinate space to this, so it has to be tracked rather than
  // assumed.
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 })

  // ── Clip state ───────────────────────────────────────────────────
  // `duration` is 0 until metadata arrives; the controls are disabled until it
  // does rather than letting someone drag a scrubber with no range. `clipError`
  // is the honest end state — a black rectangle with working controls is the
  // worst version of a missing video, because it looks like the clip is simply
  // dark.
  const [playing, setPlaying] = useState(false)
  const [clipError, setClipError] = useState(null)

  // The clip's length lives in App for the same reason `currentFrame` does:
  // more than one panel is a reading of it. The mission event log needs it to
  // know which frame the clip ENDS on — the last frame carrying a detection is
  // not the last frame of the footage — and this panel needs it for the
  // scrubber's range. Two panels holding their own copy is how a summary line
  // fires at a different moment from the one the scrubber calls the end.
  const duration = clipDuration

  // Kept in a ref so the clock effect below never needs to tear down and
  // restart just because App re-rendered with a new callback identity.
  const onFrameChangeRef = useRef(onFrameChange)
  useEffect(() => {
    onFrameChangeRef.current = onFrameChange
  })

  const fps = config.clip_fps

  // The scrubber's range. Derived from the clip's true duration once it is
  // known, NOT from the detection index: the last frame carrying a detection
  // is not the last frame of the clip, and a scrubber that stopped there would
  // make the tail of the footage unreachable. Before metadata arrives the index
  // is the only length available, so it stands in.
  const lastFrame =
    duration > 0 ? Math.max(0, Math.round(duration * fps) - 1) : index.maxFrame

  const ready = duration > 0 && clipError === null

  // ── Playback clock ───────────────────────────────────────────────
  // requestVideoFrameCallback fires once per frame actually presented and
  // hands back a precise mediaTime. Where it is missing we fall back to
  // requestAnimationFrame; both beat the `timeupdate` event, which only fires
  // about four times a second and would make the overlay visibly lag.
  //
  // It also fires on a SEEK while paused, because seeking presents a frame —
  // which is what makes scrubbing update the map and the table without a
  // second code path.
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const useVideoCallback = typeof video.requestVideoFrameCallback === 'function'
    let handle = 0
    let stopped = false

    const tick = (_now, metadata) => {
      if (stopped) return
      const mediaTime = metadata ? metadata.mediaTime : video.currentTime
      onFrameChangeRef.current(Math.max(0, Math.floor(mediaTime * fps)))
      schedule()
    }

    const schedule = () => {
      handle = useVideoCallback
        ? video.requestVideoFrameCallback(tick)
        : requestAnimationFrame(tick)
    }

    schedule()
    return () => {
      stopped = true
      if (useVideoCallback) video.cancelVideoFrameCallback(handle)
      else cancelAnimationFrame(handle)
    }
  }, [fps])

  // ── Track the displayed size ─────────────────────────────────────
  // The picture is CONTAINED in the frame, and the contained size is computed
  // here rather than left to CSS `aspect-ratio`. Two reasons: the box is
  // constrained by both the column's width and the row's leftover height, which
  // `aspect-ratio` alone does not resolve without distorting one of them; and
  // the canvas needs the result in pixels regardless, so computing it once and
  // laying the picture out from the same number keeps the overlay geometry and
  // the video in exact agreement.
  useEffect(() => {
    const frame = frameRef.current
    if (!frame) return
    const aspect = config.source_width / config.source_height
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      const pictureWidth = Math.max(0, Math.min(width, height * aspect))
      setStageSize({ width: pictureWidth, height: pictureWidth / aspect })
    })
    observer.observe(frame)
    return () => observer.disconnect()
  }, [config.source_width, config.source_height])

  // ── Controls ─────────────────────────────────────────────────────
  // `playing` follows the video's own play/pause events rather than being set
  // by the buttons. The element pauses for reasons the buttons never see — a
  // stall, a seek, the browser's own policy — and a button that flipped its
  // own icon would then be lying about the state of the clip.
  const togglePlay = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) video.play().catch(() => {})
    else video.pause()
  }, [])

  /** Seek to a frame. The frame index is the source of truth, not the time. */
  const seekToFrame = useCallback(
    (frame) => {
      const video = videoRef.current
      if (!video) return
      const clamped = Math.min(Math.max(0, frame), lastFrame)
      // Half a frame in, so rounding cannot land the seek on the previous one.
      video.currentTime = (clamped + 0.5) / fps
      // Reported immediately rather than waiting for the seek to present a
      // frame: dragging the scrubber has to move the map and the table now,
      // not a beat later. The clock corrects it on the next presented frame,
      // which is the same value.
      onFrameChangeRef.current(clamped)
    },
    [fps, lastFrame],
  )

  // ── Draw the overlay ─────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    const { width, height } = stageSize
    if (!canvas || width === 0 || height === 0) return

    // Back the canvas at device resolution so 1px strokes and labels stay
    // sharp, then work in CSS pixels for everything below.
    const dpr = window.devicePixelRatio || 1
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)

    const ctx = canvas.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, width, height)

    // Source coordinate space -> displayed size. Deliberately derived from the
    // declared source dimensions, not from video.videoWidth/videoHeight: the
    // two are not the same for this clip and there is no guarantee they ever
    // will be.
    const scaleX = width / config.source_width
    const scaleY = height / config.source_height

    // Colours and type come from tokens.css via the computed root style — a
    // canvas cannot resolve `var()`, so this is the one place they are read
    // rather than referenced. The fallbacks are shape, not palette: they only
    // matter in the first frames before the stylesheet has applied.
    const survivorColor = token(SURVIVOR)
    const labelInk = token(ON_SURVIVOR)
    const haloColor = token(SELECTION_HALO)
    if (!survivorColor) return

    const labelSize = token('--step-0') || '11px'
    const dataFont = token('--font-data') || 'monospace'
    ctx.font = `600 ${labelSize} ${dataFont}`
    ctx.textBaseline = 'middle'

    const LABEL_HEIGHT = 16
    const LABEL_PAD_X = 4

    // Selecting a survivor on the map dims everything else rather than hiding
    // it. The other detections are still real and the frame's raw count in the
    // header still includes them — a box that vanished when a pin was clicked
    // would make the header look wrong.
    const hasSelection = selectedTrackId !== null

    for (const detection of detectionsAt(index, currentFrame)) {
      const [x1, y1, x2, y2] = detection.bbox
      const x = x1 * scaleX
      const y = y1 * scaleY
      const boxWidth = (x2 - x1) * scaleX
      const boxHeight = (y2 - y1) * scaleY

      // -1 means the tracker gave this detection no ID. It is still a real
      // detection, so it is drawn — dashed, to show it cannot be counted as a
      // distinct survivor.
      const tracked = detection.track_id !== -1
      const selected = tracked && detection.track_id === selectedTrackId

      ctx.globalAlpha = !hasSelection || selected ? 1 : 0.3

      // The selected box gets a halo underneath the cyan stroke. Cyan on cyan
      // cannot carry "this one" on its own, and the priority ramp is not
      // available to borrow from — those colours mean rank, and a box that
      // turned orange when it was clicked would read as a change in priority.
      if (selected) {
        ctx.strokeStyle = haloColor
        ctx.lineWidth = 5
        ctx.setLineDash([])
        ctx.strokeRect(x, y, boxWidth, boxHeight)
      }

      ctx.strokeStyle = survivorColor
      ctx.lineWidth = selected ? 3 : 2
      ctx.setLineDash(tracked ? [] : [4, 3])
      ctx.strokeRect(x, y, boxWidth, boxHeight)
      ctx.setLineDash([])

      const label = tracked ? `#${detection.track_id}` : 'untracked'
      const labelWidth = ctx.measureText(label).width + LABEL_PAD_X * 2
      // Sit the label above the box, or inside its top edge when the box is
      // already touching the top of the frame.
      const labelY = y - LABEL_HEIGHT >= 0 ? y - LABEL_HEIGHT : y

      ctx.fillStyle = survivorColor
      ctx.fillRect(x, labelY, labelWidth, LABEL_HEIGHT)
      ctx.fillStyle = labelInk
      ctx.fillText(label, x + LABEL_PAD_X, labelY + LABEL_HEIGHT / 2)
    }

    ctx.globalAlpha = 1
  }, [stageSize, currentFrame, index, selectedTrackId, config.source_width, config.source_height])

  // Whether the selected survivor is actually visible right now. Selecting a
  // pin for someone the drone passed forty frames ago should say so, not leave
  // the viewer hunting the frame for a highlight that is not there.
  const selectedInFrame =
    selectedTrackId !== null &&
    detectionsAt(index, currentFrame).some((d) => d.track_id === selectedTrackId)

  const played = lastFrame > 0 ? (Math.min(currentFrame, lastFrame) / lastFrame) * 100 : 0

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex shrink-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="eyebrow">Detection feed</h2>
        <span className="figure text-eyebrow text-ink-muted">
          replay of stored detections · no live inference
        </span>
      </div>

      {/* The frame: the column's full width, and whatever height the row has
          left after the controls. The picture is letterboxed inside it rather
          than setting the panel's height — the four operational panels have to
          fit above the fold at 1280×720, so the video takes the space that is
          left rather than the space its aspect ratio would prefer. Frame and
          page ground are both surface-0, so the bars are invisible. */}
      <div
        ref={frameRef}
        className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-t-lg border border-edge bg-surface-0"
      >
        {/* The picture, at the source coordinate space's aspect ratio — not the
            video file's. Boxes are drawn in that space, so the picture is
            stretched to fit it rather than the other way round, which is what
            keeps the overlay geometry exact and self-consistent. */}
        <div
          className="relative"
          style={{ width: stageSize.width, height: stageSize.height }}
        >
          <video
            ref={videoRef}
            src={CLIP_SRC}
            className="absolute inset-0 h-full w-full object-fill"
            muted
            loop
            playsInline
            preload="auto"
            onLoadedMetadata={(event) => {
              onDurationChange(event.currentTarget.duration || 0)
              setClipError(null)
            }}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onError={() =>
              setClipError('The clip could not be loaded from /demo_clip.mp4')
            }
          />
          <canvas
            ref={canvasRef}
            className="pointer-events-none absolute inset-0 h-full w-full"
            style={{ width: '100%', height: '100%' }}
          />
        </div>

        {/* Loading. The overlay and every count below are driven by the
            playback clock, so until the clip has a duration there is nothing
            for them to be a reading OF — say so rather than showing a black
            rectangle that looks like footage of a dark scene. */}
        {!ready && !clipError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-surface-1">
            <div className="skeleton h-2 w-40" />
            <p className="text-fine text-ink-muted">Loading clip…</p>
          </div>
        )}

        {/* Error. Stated as a fact about the file, with the path in it, so the
            first thing anyone checks is the right thing. */}
        {clipError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface-1 px-6 text-center">
            <p className="text-body font-semibold text-ink">Clip unavailable</p>
            <p className="text-fine text-ink-soft">{clipError}</p>
            <p className="text-eyebrow text-ink-muted">
              Detections and survivor positions below are unaffected — they do
              not come from the video.
            </p>
          </div>
        )}
      </div>

      {/* ── Playback controls ─────────────────────────────────────────
          Denominated in frames, because the whole dashboard is. The scrubber
          is survivor cyan (see index.css) — it is a playback control, and
          there is no priority meaning to misread from it. */}
      <div className="flex shrink-0 items-center gap-3 rounded-b-lg border border-t-0 border-edge bg-surface-1 px-3 py-2.5">
        <ControlButton
          onClick={togglePlay}
          disabled={!ready}
          label={playing ? 'Pause' : 'Play'}
          wide
        >
          {playing ? (
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
              <rect x="3" y="2" width="4" height="12" rx="1" />
              <rect x="9" y="2" width="4" height="12" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
              <path d="M4 2.5v11a.5.5 0 0 0 .77.42l8.5-5.5a.5.5 0 0 0 0-.84l-8.5-5.5A.5.5 0 0 0 4 2.5Z" />
            </svg>
          )}
        </ControlButton>

        <ControlButton
          onClick={() => seekToFrame(currentFrame - STEP_FRAMES)}
          disabled={!ready}
          label="Step back one frame"
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
            <path d="M11.5 2.5v11a.5.5 0 0 1-.77.42L4 9.4v4.1a.5.5 0 0 1-1 0v-11a.5.5 0 0 1 1 0v4.1l6.73-4.52a.5.5 0 0 1 .77.42Z" />
          </svg>
        </ControlButton>

        <ControlButton
          onClick={() => seekToFrame(currentFrame + STEP_FRAMES)}
          disabled={!ready}
          label="Step forward one frame"
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
            <path d="M4.5 2.5v11a.5.5 0 0 0 .77.42L12 9.4v4.1a.5.5 0 0 0 1 0v-11a.5.5 0 0 0-1 0v4.1L5.27 2.08a.5.5 0 0 0-.77.42Z" />
          </svg>
        </ControlButton>

        <input
          type="range"
          className="scrub min-w-0 flex-1"
          min={0}
          max={lastFrame}
          step={1}
          value={Math.min(currentFrame, lastFrame)}
          disabled={!ready}
          onChange={(event) => seekToFrame(Number(event.target.value))}
          aria-label="Scrub through the clip by frame"
          aria-valuetext={`Frame ${currentFrame} of ${lastFrame}`}
          // Drives the filled portion of the track. One paint, no second
          // element to keep in step with the clock.
          style={{ '--played': `${played}%` }}
        />

        {/* The frame counter. Frame first and largest, because it is the index
            every other panel is keyed on; the timecode is the human reading of
            the same instant, kept beside it rather than instead of it. */}
        <div className="flex shrink-0 items-baseline gap-1.5 tabular-nums">
          <span className="eyebrow">Frame</span>
          <span className="figure text-body font-semibold text-ink">{currentFrame}</span>
          <span className="figure text-fine text-ink-muted">/ {lastFrame}</span>
        </div>

        <div className="figure shrink-0 text-eyebrow text-ink-muted">
          {timecode(currentFrame / fps)} / {timecode(duration)}
        </div>
      </div>

      {/* The in-frame detection count used to sit here too. It now lives in
          the header, where it is labelled against the survivor count it must
          not be confused with. Repeating it would be harmless — same lookup —
          but two copies of a number invite the reader to check they match. */}
      <div className="mt-2 flex shrink-0 flex-wrap gap-x-6 gap-y-1 text-eyebrow text-ink-muted">
        <span className="figure">
          {fps} fps declared clip rate — frame index is derived from it, not measured
        </span>
        {selectedTrackId !== null && !selectedInFrame && (
          <span className="figure text-ink-soft">
            Track #{selectedTrackId} is not in this frame
          </span>
        )}
      </div>
    </section>
  )
}

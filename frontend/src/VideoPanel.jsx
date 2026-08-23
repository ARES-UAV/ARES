import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CLIP_SRC,
  FPS,
  SOURCE_HEIGHT,
  SOURCE_WIDTH,
  SURVIVOR_COLOR,
  SURVIVOR_LABEL_TEXT,
} from './config.js'

/**
 * The demo clip with its detection overlay.
 *
 * Two stacked layers at identical size: a <video> and a transparent <canvas>.
 * The canvas is pointer-events-none so the video's native controls stay
 * clickable through it.
 *
 * This component does not own the playback clock — it reports the current
 * frame upward via `onFrameChange` and renders whatever `currentFrame` it is
 * given back. Other panels (map, survivor table) read the same value from App,
 * which is what keeps every count on the dashboard reconciled.
 */
export default function VideoPanel({ detections, currentFrame, onFrameChange }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const stageRef = useRef(null)

  // The stage's CSS size. Bounding boxes are scaled from the source coordinate
  // space to this, so it has to be tracked rather than assumed.
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 })

  // frame_id -> detections. Rebuilt only when the detections array changes;
  // the draw loop then does a single map lookup per frame instead of a full
  // scan of a couple of thousand records 24 times a second.
  const byFrame = useMemo(() => {
    const map = new Map()
    for (const d of detections) {
      const existing = map.get(d.frame_id)
      if (existing) existing.push(d)
      else map.set(d.frame_id, [d])
    }
    return map
  }, [detections])

  // Kept in a ref so the clock effect below never needs to tear down and
  // restart just because App re-rendered with a new callback identity.
  const onFrameChangeRef = useRef(onFrameChange)
  useEffect(() => {
    onFrameChangeRef.current = onFrameChange
  })

  // ── Playback clock ───────────────────────────────────────────────
  // requestVideoFrameCallback fires once per frame actually presented and
  // hands back a precise mediaTime. Where it is missing we fall back to
  // requestAnimationFrame; both beat the `timeupdate` event, which only fires
  // about four times a second and would make the overlay visibly lag.
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const useVideoCallback = typeof video.requestVideoFrameCallback === 'function'
    let handle = 0
    let stopped = false

    const tick = (_now, metadata) => {
      if (stopped) return
      const mediaTime = metadata ? metadata.mediaTime : video.currentTime
      onFrameChangeRef.current(Math.max(0, Math.floor(mediaTime * FPS)))
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
  }, [])

  // ── Track the displayed size ─────────────────────────────────────
  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setStageSize({ width, height })
    })
    observer.observe(stage)
    return () => observer.disconnect()
  }, [])

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
    // declared SOURCE_* constants, not from video.videoWidth/videoHeight: the
    // two are not the same for this clip and there is no guarantee they ever
    // will be.
    const scaleX = width / SOURCE_WIDTH
    const scaleY = height / SOURCE_HEIGHT

    ctx.font = '600 12px ui-sans-serif, system-ui, -apple-system, sans-serif'
    ctx.textBaseline = 'middle'

    const LABEL_HEIGHT = 16
    const LABEL_PAD_X = 4

    for (const detection of byFrame.get(currentFrame) ?? []) {
      const [x1, y1, x2, y2] = detection.bbox
      const x = x1 * scaleX
      const y = y1 * scaleY
      const boxWidth = (x2 - x1) * scaleX
      const boxHeight = (y2 - y1) * scaleY

      // -1 means the tracker gave this detection no ID. It is still a real
      // detection, so it is drawn — dashed, to show it cannot be counted as a
      // distinct survivor.
      const tracked = detection.track_id !== -1

      ctx.strokeStyle = SURVIVOR_COLOR
      ctx.lineWidth = 2
      ctx.setLineDash(tracked ? [] : [4, 3])
      ctx.strokeRect(x, y, boxWidth, boxHeight)
      ctx.setLineDash([])

      const label = tracked ? `#${detection.track_id}` : 'untracked'
      const labelWidth = ctx.measureText(label).width + LABEL_PAD_X * 2
      // Sit the label above the box, or inside its top edge when the box is
      // already touching the top of the frame.
      const labelY = y - LABEL_HEIGHT >= 0 ? y - LABEL_HEIGHT : y

      ctx.fillStyle = SURVIVOR_COLOR
      ctx.fillRect(x, labelY, labelWidth, LABEL_HEIGHT)
      ctx.fillStyle = SURVIVOR_LABEL_TEXT
      ctx.fillText(label, x + LABEL_PAD_X, labelY + LABEL_HEIGHT / 2)
    }
  }, [stageSize, currentFrame, byFrame])

  const frameDetections = byFrame.get(currentFrame) ?? []

  return (
    <section>
      <div
        ref={stageRef}
        className="relative w-full overflow-hidden rounded-lg bg-black"
        // The stage is the source coordinate space's aspect ratio, not the
        // video file's. Boxes are drawn in that space, so the picture is
        // stretched to fit it rather than the other way round — that keeps the
        // overlay geometry exact and self-consistent.
        style={{ aspectRatio: `${SOURCE_WIDTH} / ${SOURCE_HEIGHT}` }}
      >
        <video
          ref={videoRef}
          src={CLIP_SRC}
          className="absolute inset-0 h-full w-full object-fill"
          controls
          muted
          loop
          playsInline
          preload="auto"
        />
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full"
          style={{ width: '100%', height: '100%' }}
        />
      </div>

      <div className="mt-2 flex gap-6 text-sm text-slate-400 tabular-nums">
        <span>
          Frame <span className="text-slate-200">{currentFrame}</span>
        </span>
        <span>
          <span className="text-slate-200">{frameDetections.length}</span> in frame
        </span>
        <span>{FPS} fps (declared)</span>
      </div>
    </section>
  )
}

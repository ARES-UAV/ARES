# Part 7 — The Frontend, File by File

About 3,900 lines across nineteen files. This part starts from "what is React"
and ends with you being able to explain why the import order in `main.jsx` is
load-bearing.

---

## 1. Web frontend fundamentals

### HTML, CSS, JavaScript

- **HTML** — structure. What elements exist.
- **CSS** — presentation. What they look like.
- **JavaScript** — behaviour. What happens when things change.

The browser turns HTML into a **DOM** — a tree of objects JavaScript can modify.
Change the DOM, the screen updates.

### Why a framework

Updating the DOM by hand gets unmanageable fast. Your dashboard has a playback
clock ticking 24 times a second and six panels that all need to reflect the
current frame. Written by hand, that is hundreds of `element.textContent = ...`
statements and a guarantee that two of them will eventually disagree.

**React** inverts it. You write a function that says *what the screen should look
like given the current state*, and React works out the minimal DOM changes to get
there.

---

## 2. React

### Components

A component is a function that returns markup:

```jsx
function ControlButton({ onClick, disabled, label, children }) {
  return (
    <button onClick={onClick} disabled={disabled} aria-label={label}>
      {children}
    </button>
  )
}
```

Used like an HTML tag: `<ControlButton label="Play" />`.

### JSX

The HTML-looking syntax inside JavaScript. It is not HTML — it compiles to
function calls. A few differences that bite:

- `className` not `class` (because `class` is a JS reserved word — the same
  collision `schemas.py` handles with an alias)
- `{}` embeds JavaScript: `<span>{survivor.track_id}</span>`
- Every component returns exactly one root element

### Props

Data passed down, parent to child. **Read-only.** A child never modifies its
props.

```jsx
<SurvivorTable survivors={survivorsFound} config={config} />
```

### State

Data a component owns and can change. Changing it triggers a re-render.

```jsx
const [currentFrame, setCurrentFrame] = useState(0)
```

`useState` returns the current value and a setter. Call the setter, React
re-renders.

### The core idea: state flows down, events flow up

`App` owns `currentFrame`. `VideoPanel` receives it *and* a callback:

```jsx
<VideoPanel currentFrame={currentFrame} onFrameChange={setCurrentFrame} />
```

The video reports the frame **up**; App stores it; every other panel receives it
**down**. That is why the map, the table and the log always show the same
instant. There is one clock.

### Hooks

| Hook | Purpose |
|---|---|
| `useState` | Component-owned state |
| `useEffect` | Run code after render — fetches, subscriptions, cleanup |
| `useMemo` | Cache an expensive computation until its inputs change |
| `useCallback` | Cache a function so children don't re-render needlessly |
| `useRef` | A mutable box that survives re-renders without triggering one |

**`useEffect`'s dependency array** controls when it runs:

```jsx
useEffect(() => {
  fetchDetections().then(setDetections)
}, [])          // [] = run once, on mount
```

**`useMemo`** avoids recomputing on every render:

```jsx
const index = useMemo(() => buildDetectionIndex(detections ?? []), [detections])
```

Without this, the detection index would be rebuilt 24 times a second as the frame
advances — for a value that only changes when `detections` does.

### StrictMode

```jsx
<StrictMode><App /></StrictMode>
```

In development, React deliberately **double-invokes** effects and renders to
surface bugs caused by impure code or missing cleanup. It does not do this in
production. If you see something happen twice in dev, this is usually why.

---

## 3. The build tooling

### Vite

The dev server and bundler.

- **Dev:** serves your source directly using native ES modules. Startup is
  instant, and **HMR** (Hot Module Replacement) swaps a changed module without
  reloading the page or losing state.
- **Build:** `npm run build` bundles and minifies everything into
  `frontend/dist/`.

Your `vite.config.js` is minimal:

```js
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
})
```

**Note what is absent: there is no proxy.** The frontend talks to the backend by
absolute URL, from `config.js`:

```js
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
```

This is why CORS matters — two different origins — and why pointing at a
different backend is an env variable rather than a config edit.

### Tailwind CSS

Utility-first CSS. Instead of writing a stylesheet, you compose classes:

```jsx
<div className="flex flex-col gap-3 px-4 pt-3 pb-3">
```

`flex` + `flex-col` = vertical flexbox. `gap-3` = spacing between children.
`px-4` = horizontal padding.

**The argument for it here:** styles live next to the markup, so there is no
hunting through a stylesheet for the rule that governs an element, and no
gradually-accumulating pile of dead CSS.

Your `index.css` publishes the design tokens as Tailwind utilities via
`@theme inline`, which is what makes `bg-surface-0` and `text-ink` work.

### Leaflet

An open-source mapping library. Tiles, markers, zoom, pan.

**Chosen because it needs no API key** — CLAUDE.md constraint 4. Google Maps and
Mapbox both require one. OpenStreetMap tiles through Leaflet do not.

---

## 4. `main.jsx` — the import order is load-bearing

Thirty-six lines, and most of them are a comment explaining four import
statements. That comment is worth understanding because it encodes a bug that was
actually hit.

```js
import './tokens.css'
import './fonts.css'
import 'leaflet/dist/leaflet.css'
import './index.css'
```

**Why this exact order:**

1. **`tokens.css` first** — it defines the custom properties every other
   stylesheet references. It is also what makes "no raw hex outside this file" a
   rule with one obvious place to check.

2. **`fonts.css`** — `@font-face` declarations pointing at files in
   `public/fonts/`. **There is no `<link>` to Google Fonts anywhere in this
   project**, because the dashboard has to render correctly with no network.

3. **`leaflet.css` before `index.css`** — and this is the real one. `index.css`
   re-skins Leaflet's controls in your tokens, and those rules **tie** with
   Leaflet's own on CSS specificity. **A tie is broken by source order.** When
   Leaflet's stylesheet was imported from inside `MapPanel.jsx`, it loaded last
   and won — and the zoom buttons and scale bar stayed white on a near-black
   dashboard.

4. **`index.css` last** — it imports Tailwind and publishes the tokens as
   utilities, so it must come after the tokens it names, and it carries the
   Leaflet overrides, so it must come after Leaflet.

**The general lesson:** when two CSS rules have equal specificity, the one that
appears later wins. Import order is therefore program logic, not housekeeping.

---

## 5. `tokens.css` — the palette, and why it was rebuilt

94 lines. Every colour in the dashboard is defined here and nowhere else.

### What was wrong the first time

You said the colours "look AI generated." They did, and there were two measurable
reasons, both recorded at the top of the file:

**1. The palette was Tailwind's `-400` steps** — `cyan-400`, `green-400`,
`amber-400`, `orange-400`, `red-400`. Those are tuned for **light** surfaces.
Every one of them failed the dark-mode lightness band on a `#0B1013` ground.

**2. Priority was a green → amber → orange → red rainbow.** Two failures at once:

- A **rainbow ramp for ordered data.** Rainbows have no perceptual ordering —
  nothing tells you amber is "more" than green except convention.
- A **red-green ramp**, which collapses for roughly 8% of men.

And measured: "serious" `#fb923c` against "critical" `#f87171` sat at **ΔE 10.6**
— below the 15 floor. Even a viewer with full colour vision struggles to tell the
two most urgent bands apart. **On a rescue dashboard that is a real defect**, not
an aesthetic quibble.

### What replaced it

```css
--surface-0: #0B1013;   /* page ground */
--surface-1: #121A1E;   /* panels */
--surface-2: #1A252A;   /* raised: rows, chips, hover */

--ink:       #E6EDEF;   /* not pure white — full white on near-black glares */
--ink-soft:  #A8B8BE;
--ink-muted: #6B7F87;

--survivor:  #22A7BD;   /* ONE job: survivor detections. Never text. */

--priority-low:      #FFCE9E;   /* ordinal ramp: one hue, light → dark */
--priority-medium:   #FB9A4A;
--priority-high:     #E06A1F;
--priority-critical: #A8410C;

--hazard:    #D63A5C;   /* reserved, deliberately outside the ramp */
```

### The three rules encoded here

**1. Survivor cyan has exactly one job.** Bounding boxes, map pins, selection
edges, the scrubber. **Never text, never a priority band.** Every row in the
survivor table is a survivor, so colouring priority in cyan would say nothing —
and a cyan number reads as a *category* rather than a *value*.

Its ΔE against every priority step is 18–22 under colour-vision deficiency, 28–30
under normal vision. Comfortably separated.

**2. Priority is an ordinal ramp.** One hue, monotone light to dark, hue spread
24°, every step gap ≥ 0.06 in lightness. The ordering survives a projector, a
photocopy, and a colourblind judge — because the ordering **is** the lightness.

**3. The band name is always rendered beside the swatch.** Colour is never the
only encoding. A ramp tells you "darker than that one"; it never tells you *which
band this is*. So the word is never dropped.

### There is no "clear" band

`low` is the bottom of the ramp, drawn in a pale alarm colour rather than green.
**The lowest-priority person in a disaster zone still needs rescuing**, and a
green survivor row would tell an operator otherwise.

That is the single best palette decision in the project and it is worth saying
out loud in the pitch.

### Typography

```css
--font-data: 'JetBrains Mono', ui-monospace, monospace;
--font-ui:   'Space Grotesk', -apple-system, sans-serif;
```

```css
.figure, .stat-value, td.num, .coord, .score {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums;
}
```

**Every figure on screen is monospace with tabular numerals**, and this is
non-negotiable: without it, digit widths change as counts update and the entire
header **visibly twitches** 24 times a second. On a dashboard whose job is to look
trustworthy, that reads as instability.

It also matters in the coordinate column — proportional digits make decimal
points wander, and a column of coordinates whose points don't line up cannot be
scanned at all.

---

## 6. `config.js` — frontend constants and the fallback

Two kinds of value, and the distinction is the point:

- **`FALLBACK_CONFIG`** — clip and camera constants the **backend** owns. Used
  only when `/api/config` is unreachable, and the header says so.
- **Everything else** — genuinely frontend-only: the palette token names, where
  the clip is loaded from, where the backend lives.

### The `min_track_frames` comment worth reading

```js
min_track_seconds: 2.5,
// 2.5 * 24. Written out rather than computed from clip_fps above: this
// whole object is a hand-kept mirror of backend/config.py, and a value that
// recomputed itself here would go on looking right after the backend's rule
// changed.
min_track_frames: 60,
```

This is the *opposite* of the rule in `backend/config.py`, where `MIN_TRACK_FRAMES`
**is** derived. And both are right, because they are solving different problems:

- The backend derives it so the rule stays consistent when `CLIP_FPS` changes.
- The frontend hardcodes it because it is a **mirror**, and a mirror that
  recomputes itself hides the fact that the original has changed.

That is a genuinely subtle distinction and a great thing to be able to explain.

### `priorityBand()` and the fail-upward rule

```js
export function priorityBand(band) {
  const key = PRIORITY_BANDS[band] ? band : LEGACY_BANDS[band]
  const known = PRIORITY_BANDS[key]
  if (known) return { ...known, name: key, color: paint(known.token) }
  return { step: PRIORITY_BANDS.critical.step, ... , label: band ?? 'Unknown' }
}
```

**An unrecognised band renders at the TOP of the ramp, not the bottom.**

The reasoning: getting this wrong in the safe-looking direction would quietly
rank someone last because a string did not match. Erring upward is the failure a
search-and-rescue dashboard should have.

`LEGACY_BANDS` maps the old names (`warning` → `medium`, `serious` → `high`) in
case Robin's version of `priority.py` is branched from before the rename — cheap
insurance against a mismatch discovered on stage.

### The two zoom ceilings

```js
export const MAP_MAX_NATIVE_ZOOM = 19   // OSM renders no tiles past this
export const MAP_MAX_ZOOM = 22          // Leaflet upscales beyond it
export const MAP_FIT_MAX_ZOOM = 20      // how far the auto-fit may go
```

Different numbers for different reasons. OSM renders nothing past zoom 19, so
nothing past 19 was ever fetched. But at 20 m altitude the camera covers only
~23 m of ground, so at zoom 19 the entire search area is about 70 px wide and
survivors land on top of each other.

`MAX_NATIVE_ZOOM` stops Leaflet requesting tiles that do not exist;
`MAX_ZOOM` lets it keep zooming by upscaling the last real tile. **The base map
goes soft, which is the honest signal that it has run out of detail while the
survivor positions have not.**

`MAP_FIT_MAX_ZOOM` is lower still, because fitting a handful of survivors metres
apart would zoom past every recognisable feature and open on a blank beige field
— technically framed on the survivors, useless for telling anyone where they are.

---

## 7. `api.js` — all backend access in one place

Every fetch goes through `getJson`, which surfaces the backend's `detail` string
rather than a bare status code.

### `loadConfig()` never throws

```js
export async function loadConfig() {
  try {
    const config = await getJson('/api/config')
    return { config, offline: false, reason: null }
  } catch (e) {
    return { config: FALLBACK_CONFIG, offline: true, reason: e.message }
  }
}
```

Every other panel can show an error state. But `config` holds the numbers the
video overlay and the map are **drawn with** — with nothing to draw against there
is no dashboard at all.

So it degrades to the bundled constants, reports that it did, and the header shows
an offline badge. **The dashboard keeps working, and it says out loud that the
figures are local rather than live.**

---

## 8. `App.jsx` — the shared state

498 lines. Everything the dashboard knows lives here.

### What it owns

| State | Why it lives here |
|---|---|
| `config` | Panels are *handed* it, so one set of numbers is in force at any moment |
| `detections` | The whole clip, fetched once |
| `survivors` | Confirmed roster, already ranked |
| `events` | Cluster and band timeline |
| `clipDuration` | Two panels are readings of it: the scrubber's range and the log's end frame |
| `currentFrame` | **The playback clock.** Every time-varying panel reads it from here |
| `selectedTrackId` | Crosses three panels — a map pin, a table row and a bounding box are one selection viewed three ways |

**The governing rule**, from the docstring:

> Panels are given numbers and lists, never the raw data to tally for themselves
> — a panel that counts for itself is a panel that can disagree with the header,
> which was the first mockup's worst flaw.

### `survivorsFound` — the roster at this instant

```jsx
const survivorsFound = useMemo(() => {
  if (survivors === null) return null
  return survivors.filter((s) => s.confirmed_frame <= currentFrame)
}, [survivors, currentFrame])
```

Three things here matter.

**It filters on `confirmed_frame`, not `first_frame`.** A track first seen at
frame 100 does not clear 2.5 seconds until frame 160. Counting it at 100 would
confirm it on evidence the clip has not played yet, and the header would run
ahead of the footage.

**It returns `null`, not `[]`, while loading.** An empty array would make the
header confidently display **0 survivors**, which is a different claim from *"not
known yet."*

**Its length IS the header's survivor count**, and it is also the table's rows.
One array, three renderings. They cannot disagree.

### The fold, and the `ResizeObserver` callback ref

The four operational panels must be reachable without scrolling at **1280×720** —
projector resolution, and the only size that actually has to work.

So the header's height is **measured**, not assumed:

```jsx
const measureHeader = useCallback((element) => {
  if (!element) return
  const observer = new ResizeObserver(([entry]) => {
    const box = entry.borderBoxSize?.[0]
    setHeaderHeight(box ? box.blockSize : entry.contentRect.height)
  })
  observer.observe(element)
  return () => observer.disconnect()
}, [])
```

**Why a callback ref rather than a ref object plus `useEffect`:** the header does
not exist on first render — `DashboardSkeleton` is returned instead. So a
`useEffect(..., [])` would run once against a `null` ref, never run again, and
leave the height at 0 forever.

**That failure is quiet and nasty.** The block below would be a full `100vh` tall
and push the bottom row clean off the screen — which is the exact thing the
measurement exists to prevent. A callback ref fires when the node actually
arrives.

**`borderBoxSize`, not `contentRect`**, because the header has a bottom border and
the block below starts under the border, not under the content.

### The layout

```jsx
<div className="flex flex-col gap-3 lg:h-[var(--ops-h)]" style={opsHeight}>
  <div className="grid lg:flex-[3] lg:grid-cols-2">   {/* video + map */}
  <div className="grid lg:flex-[2] lg:grid-cols-2">   {/* table + log */}
</div>
```

`flex-[3]` and `flex-[2]` rather than fixed pixel heights: the panels **divide
whatever the viewport gives them**, so a taller screen makes the video and map
bigger rather than leaving empty ground under the log.

`100vh` deliberately, not `100dvh` — this is a desktop dashboard on a projector,
and a mobile URL bar that never appears should not be budgeted for.

### Above the fold vs below

**Above:** video, map, survivor queue, event log. All four are things an operator
**monitors** — four readings of the same playback instant. *A reading you have to
scroll to is a reading you are not watching.*

**Below, in collapsed `<details>`:** mission parameters and the priority
reference. **Neither changes while the clip plays.** They are read once — by a
judge asking where the numbers come from — and then never again.

The `Reference` wrapper uses a plain `<details>` deliberately: keyboard-operable,
findable by browser find-in-page when open, and needing no state in App. The one
addition is that the closed summary carries the title, the provenance note and a
sentence saying what is inside. *A disclosure whose closed state says only
"details" is a disclosure nobody opens.*

### `DashboardSkeleton`

Renders the **layout**, not a spinner — panels appear where they will actually be,
at the size they will actually be, so the page does not jump when data lands. *On
a projector, a layout that reflows once after load reads as a page still being
built.*

And it is built from the "not measured" tokens: **a skeleton must not look like a
value.** A grey block that could be mistaken for a reading of zero is worse than
no dashboard at all.

It is also silent about survivors, because "0 survivors" and "not known yet" are
different claims and only one of them is true.

---

## 9. The derived-state modules

### `detectionIndex.js`

Builds every count the dashboard needs in one pass over the detections array.

```js
export function buildDetectionIndex(detections) {
  const byFrame = new Map()
  const firstFrameByTrack = new Map()
  // ...
  const trackStarts = [...firstFrameByTrack.values()].sort((a, b) => a - b)
  return { byFrame, trackStarts, trackCount, maxFrame, totalDetections }
}
```

**`uniqueTracksThrough`** answers "how many track IDs by frame N?" with a **binary
search** over the sorted start frames, rather than scanning every track on every
one of 24 frames a second.

**The asymmetry to understand:** this module computes the first two header counts
and **deliberately does not compute the third**. The confirmed survivor count is
the length of `/api/survivors`. The module's own docstring explains why the rule
changed:

> This module used to be forbidden from tallying track IDs at all, because back
> then a distinct-track-ID count and the length of the `/api/survivors` list were
> two ways of answering one question.
>
> Persistence filtering separates them into two **different questions**, and the
> distance between the answers is the point.

### `missionLog.js`

Assembles the log from two sources:

- **From the backend** — cluster formation and priority bands. Both need ground
  positions and the scoring formula.
- **From shared state** — replay start, survivor confirmations, end-of-clip
  summary. Derived from the same roster the header counts.

**That second half is the point, not an oversight.** The obvious design has the
backend emit a confirmation event per track — and then the log's confirmation
lines are a *second list of survivors* that has to agree with the header. Instead:
one line per element of the same array. **They cannot disagree because there is
nothing to disagree.**

`entriesThrough(entries, frame)` returns everything at or before the current
frame. That single rule makes scrubbing work in **both directions with no second
code path** — drag backwards and the later lines are simply no longer included.

### `clock.js`

`timecode(seconds)` and `frameTimecode(frame, fps)` → `mm:ss.d`.

**Tenths**, because the clip is seconds long: whole seconds would put a dozen log
lines on the same stamp, and hundredths would be precision the frame index beside
it already carries better.

Returns a **same-width placeholder** (`--:--.-`) rather than throwing or rendering
`NaN`. A timestamp column that changes width makes the whole log shuffle
sideways.

And these are readings of the **clip**, never the wall clock. `new Date()` has
nothing to do with where the drone was.

### `theme.js`

Two things on this dashboard cannot use a CSS variable:

- **The video overlay** — a canvas 2D context takes `strokeStyle` as a colour
  *string*. It is not CSS; `var(--survivor)` means nothing to it.
- **Leaflet markers** — circle styles are SVG presentation attributes, and
  `var()` is not resolved in an attribute value in any browser you would demo on.

So `token(name)` reads the computed value off `:root`. **That keeps `tokens.css`
the single place a colour is written down.**

Values are cached because there is no theme switch. But an **empty result is
deliberately not cached** — it means the stylesheet had not applied yet, and the
next call should try again rather than remember the miss forever.

---

## 10. The six panels

### `HeaderBar.jsx`

Two rows: an identity row above four stat cells. **This split is a layout decision
made for 1280px** — six stat cells in one strip needed ~1250px before wrapping
into a ragged second line.

It shows the three counts side by side, because:

> Showing only the ID count would overstate the survivors by an order of
> magnitude; showing only the confirmed count would hide what the filter is doing
> and leave a judge no way to check it.

It **computes nothing.** It is handed the numbers.

### `VideoPanel.jsx`

Two stacked layers at identical size: a `<video>` and a transparent `<canvas>`.
The canvas draws the bounding boxes for the current frame.

**Why the controls are custom rather than native `<video controls>`:** the native
bar is a different shape on every browser, sits over the bottom of the overlay,
and — the reason that actually matters — **has no concept of a frame.** The demo
is a frame-indexed replay. A judge asking "go back to the one at frame 300" needs
a frame number to scrub against.

So the scrubber is denominated in **frames**, and the video's `currentTime` is
derived from it — the same direction the rest of the dashboard reasons in.

It does not own the clock, the detection index, or the clip geometry. All three
come from App.

### `MapPanel.jsx`

Leaflet, driven **imperatively** rather than through a React wrapper. It owns its
own DOM subtree and event loop, and *one more dependency between here and the map
is one more thing that can break on 5 September.*

**Markers are circles, not Leaflet's default pin.** Partly practical — a circle
takes an arbitrary fill; the default pin is a fixed blue PNG whose asset path is a
known bundler trap. And partly meaning: **a pin points at a surveyed point**, and
these positions are a flat-earth estimate from an assumed altitude. *A soft circle
reads as "about here", which is the truth.*

The wording note is worth reading twice:

> They are counts of CONFIRMATION, not of localization success. "6 of 9 located"
> read as "localization worked for 6 of them", which is a bug report about a
> system that is working correctly.

### `SurvivorTable.jsx`

Rows are the `survivors` prop and nothing else — the same array the header counts.

**The list arrives already ranked.** `/api/survivors` returns it sorted by
priority descending. *Re-sorting here would be a second opinion on rescue order,
and there should only be one.*

Selection calls the same `onSelectTrack` a map marker calls, with the same
toggle-to-clear behaviour.

### `EventLogPanel.jsx`

Styled as a terminal, because that is what it is: monospace, append-only, newest
at the bottom.

**Colour appears only in a left gutter stripe:**

- survivor cyan → detection events (confirmed, cluster formed)
- the priority ramp → band events, in the band being reported
- muted ink → system lines

A stripe rather than coloured text, because `tokens.css` states the rule that
survivor cyan is never a text colour.

**Scrubbing:** the visible set is everything at or before `currentFrame`. Drag
backwards and later lines are gone — *a log that kept them would be describing a
frame the operator is no longer looking at.*

### `MissionParameters.jsx`

**This panel exists instead of a UAV telemetry bar**, and that is the whole point:

> There is no aircraft: no battery to read, no GPS receiver to report a fix, no
> radio link whose quality could be strong or weak, no onboard storage filling
> up, no flight mode, no weather. A bar showing any of those would be six
> invented numbers dressed as instrument readings — the same failure as
> hand-authoring detections, and a judge only has to ask "what is this connected
> to?" once.

Instead it shows the constants, each tagged with **provenance**:

| Tag | Meaning |
|---|---|
| **assumed** | A fixed per-clip constant standing in for a measurement the prototype cannot make — altitude, FOV, flight track, GPS origin |
| **chosen** | An operating decision, not a guess about the world — `imgsz`, confidence threshold. What's open to question is whether it was a *good* choice |
| **derived** | Arithmetic on the assumed values. Inherits their uncertainty; the formula is printed beside it |
| **measured** | An actual observation. Exactly one row can ever earn this, and it has not yet |

**The tags are drawn in no colour of their own** — survivor cyan means "this is a
detection" and the priority ramp means rank, so borrowing either would say
something false about a table of constants.

That four-way provenance distinction is, honestly, the most sophisticated idea on
your dashboard. It is worth pointing at directly in the pitch.

### `PriorityReference.jsx`

The ramp legend, the cut points, the formula, and `HysteresisNote` — which states
the margin with a worked example computed from config: *critical starts at 0.78,
falls back at 0.72, and a score can sit past a printed threshold in the band
below.* It ends **"It delays a band change; it never hides one."**

When the cluster term was dropped, it says so in the numbers on screen: *23
survivors, every one with the same 22 neighbours within 15 m → one group → term
can't rank → dropped, confidence alone ranks this footage.*

A `null` survivors list is a **third state**, not a "no" — with the backend off,
the panel states the weights without claiming what this clip did with them.

---

## 11. The design rules, collected

1. **Counts reconcile because they are one number, not two that agree.**
2. **Survivor cyan marks detections only.** Never text, never a band.
3. **Priority is an ordinal ramp**, always with its label.
4. **No green.** The lowest-priority person still needs rescuing.
5. **No invented telemetry.** There is no aircraft.
6. **Every figure is monospace with tabular numerals.**
7. **Time-varying panels are above the fold and never behind a click.**
8. **A skeleton must not look like a value.** `null` ≠ `0`.
9. **Provenance is displayed:** assumed / chosen / derived / measured.
10. **No network at render time.** Fonts are local, tiles are cached.

---

## What to take from this part

- React: state flows down, events flow up. **One clock in App**, and every panel
  reads it.
- The import order in `main.jsx` is program logic — a CSS specificity tie is
  broken by source order.
- The palette was **measured, not tasted**: ΔE 10.6 between the two most urgent
  bands was a real defect.
- `survivorsFound.length` is the header count *and* the table rows *and* the map
  count. One array.
- The `ResizeObserver` is a **callback ref** because the header doesn't exist on
  first render.
- `MissionParameters` exists instead of fake telemetry, and its four provenance
  tags are the most defensible idea on the screen.

**Next:** Part 8 — the tools directory and every command you ran.

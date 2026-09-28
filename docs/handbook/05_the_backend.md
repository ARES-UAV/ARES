# Part 5 — The Backend, File by File

Seven Python files, about 1,540 lines including comments. This part starts from
"what is a web API" and ends with you being able to trace a single HTTP request
through every function it touches.

---

## 1. Web fundamentals, from zero

### What a server is

A **server** is a program that sits waiting for requests and sends back
responses. Your backend is a server. It runs on your laptop, listens on port
8000, and answers questions the dashboard asks it.

### HTTP

The protocol browsers and servers speak. A request has:

- A **method** — `GET` (fetch something), `POST` (send something), `PUT`,
  `DELETE`. Your backend is entirely `GET`; it never modifies anything.
- A **path** — `/api/survivors`
- **Headers** — metadata
- Optionally a **body**

A response has a **status code**, headers, and a body:

| Code | Meaning | Where yours uses it |
|---|---|---|
| 200 | OK | Every successful response |
| 404 | Not found | A map tile outside the cached box |
| 422 | Validation failed | FastAPI rejects a malformed path parameter |
| 500 | Server error | `detections.json` isn't valid JSON |
| 503 | Unavailable | `detections.json` doesn't exist at all |

### Ports and localhost

`localhost` is your own machine. `:8000` is a **port** — a numbered door. Your
backend listens on 8000, the frontend dev server on 5173. Two programs, two
doors, one machine.

### REST and JSON

**REST** is a convention: URLs name *resources*, HTTP methods name *actions*.
`GET /api/survivors` reads as "give me the survivors." Yours follows it.

**JSON** is the data format — nested objects, arrays, numbers, strings. Both
Python and JavaScript read and write it natively, which is why it is the seam
between your backend and your frontend, and also the seam between you and Robin.

---

## 2. The stack

### FastAPI

The web framework. You define a function, decorate it with a route, and FastAPI
handles the HTTP:

```python
@app.get("/api/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", service="ares-backend", version=VERSION)
```

That is the whole endpoint. FastAPI parses the request, calls your function,
validates the return value against `Health`, serialises it to JSON and sends it.

**Why FastAPI and not Flask or Django:**

- Type hints drive validation. The annotation is not documentation, it is enforced.
- Automatic interactive docs at `/docs` — **open this, it is genuinely useful for
  a demo**.
- Async-capable, though you don't need it.
- The whole perception stack is Python, so there is no serialisation boundary
  between your teammates' code and this service.

### Uvicorn

FastAPI defines *what* to serve; **uvicorn** actually listens on the port. It is
an ASGI server — the async successor to WSGI.

```bash
uvicorn backend.main:app --reload --port 8000
```

| Part | Meaning |
|---|---|
| `backend.main` | The Python module (`backend/main.py`) |
| `:app` | The variable inside it — your `FastAPI()` instance |
| `--reload` | Restart automatically when a file changes. Development only |
| `--port 8000` | The door to listen on |

`backend/__init__.py` is empty and exists so Python treats `backend/` as a
package, which is what makes `backend.main` importable. This is also why you run
uvicorn **from the repo root**, not from inside `backend/` — the error
`ModuleNotFoundError: No module named 'backend'` means you're in the wrong
directory.

### Pydantic

Data validation via type annotations. You describe the shape; Pydantic enforces
it.

```python
class Detection(BaseModel):
    frame_id: int = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
```

`ge=0` means "greater than or equal to 0". A record with `confidence: 1.4` is
rejected with a clear error rather than quietly producing a nonsense priority
score.

**Why this matters here specifically:** `detections.json` comes from a model run.
If something goes wrong upstream, you want to know at the boundary, not three
layers deep when a survivor appears at latitude 4,000.

### CORS

Browsers enforce the **same-origin policy**: a page served from
`localhost:5173` may not, by default, fetch from `localhost:8000`. Different
port, different origin.

**CORS** — Cross-Origin Resource Sharing — is the server saying "this origin is
allowed."

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,   # localhost:5173 and 127.0.0.1:5173
    ...
)
```

Without this the dashboard shows empty panels and the browser console shows CORS
errors. It is the single most common reason a working backend appears broken.

---

## 3. `backend/config.py` — every number in one place

**Purpose:** everything a judge might ask "where does that number come from?"
about lives here, not scattered through the code.

That is not tidiness. It is a demo strategy. When someone asks about the
confidence threshold you open one file, and the answer is written above the
constant.

### The constants

```python
# Paths
DETECTIONS_PATH = DATA_DIR / "detections.json"
TILES_DIR       = DATA_DIR / "tiles"

# Detection
CONFIDENCE_THRESHOLD     = 0.18    # high recall — a missed survivor is unrecoverable
MAX_DETECTIONS_PER_FRAME = 1000    # not the default 300
DETECTION_IMGSZ          = 960     # chosen from a measured sweep

# Clip geometry
FRAME_WIDTH  = 1280
FRAME_HEIGHT = 720
CLIP_FPS     = 24.0
ALTITUDE_M     = 20.0
CAMERA_FOV_DEG = 60.0
ORIGIN_LAT     = 26.405892
ORIGIN_LON     = 92.233479

# Assumed flight track
DRONE_SPEED_MS    = 5.0
DRONE_HEADING_DEG = 45.0           # compass bearing: 0 = N, 90 = E

# Persistence
MIN_TRACK_SECONDS = 2.5
MIN_TRACK_FRAMES  = int(MIN_TRACK_SECONDS * CLIP_FPS)

# Priority
WEIGHT_CONFIDENCE       = 0.4
WEIGHT_CLUSTER_SIZE     = 0.3
WEIGHT_HAZARD_PROXIMITY = 0.3
CLUSTER_RADIUS_M        = 15.0
CLUSTER_SATURATION      = 4
HAZARDS                 = []       # EMPTY ON PURPOSE
HAZARD_INFLUENCE_M      = 50.0

# Bands
PRIORITY_MEDIUM_AT   = 0.25
PRIORITY_HIGH_AT     = 0.50
PRIORITY_CRITICAL_AT = 0.75
BAND_HYSTERESIS      = 0.03

# Event log
EVENT_SAMPLE_INTERVAL_S = 1.0

# Benchmark
DEVICE_FPS  = None                 # not yet measured
DEVICE_NAME = "Raspberry Pi 4 Model B"
```

### Three of these deserve special attention

**`HAZARDS = []`.** Empty, and it must stay empty until the hazard classifier
produces real positions. Inventing a fire to make the map look busy is the same
failure as hand-authoring detections. While it is empty, `priority.py` **drops**
the hazard term and renormalises the other two.

**`CLUSTER_SATURATION = 4`.** The neighbour count at which the cluster term
saturates at 1.0. Beyond four, five-together and nine-together are both "a
crowd." Without a ceiling, one large group would flatten every other survivor's
cluster score to nearly nothing.

**The band thresholds are the quarters of the range.** 0.25 / 0.50 / 0.75. That
is the whole rule. A judge asking "why 0.75?" gets an answer in one sentence,
which no hand-tuned number was ever going to give. They are deliberately *not*
fitted to the current clip's score distribution — thresholds chosen to make a
demo look colourful are the same failure as fabricated data.

### Why derived values are derived, not typed

```python
MIN_TRACK_FRAMES = int(MIN_TRACK_SECONDS * CLIP_FPS)
```

Not `60`. If someone changes `CLIP_FPS`, the frame count follows. A typed 60
would go on looking right after the rule underneath it changed.

---

## 4. `backend/schemas.py` — the API's type system

Five Pydantic models. Each one is a contract.

### `Detection`

Mirrors the team JSON contract exactly.

```python
class Detection(BaseModel):
    frame_id: int = Field(..., ge=0)
    bbox: List[float] = Field(..., min_length=4, max_length=4)
    confidence: float = Field(..., ge=0.0, le=1.0)
    track_id: int
    class_id: int = Field(0, alias="class")

    model_config = {"populate_by_name": True}
```

**The `alias` is worth understanding.** `class` is a reserved word in Python — you
cannot name a field `class`. But the JSON contract says `class`, and the contract
is not yours to change. So the Python attribute is `class_id` and the alias maps
it to `class` on the wire.

This is a small thing that shows a real principle: **the contract wins over
language convenience.**

### `ClipConfig`

The constants, as one object, sent to the frontend by `/api/config`.

Why this exists rather than the frontend holding its own copy: the two would
drift. The frontend *does* keep a fallback copy for when the backend is
unreachable, and it shows an offline badge when it is using it — but whenever the
backend is up, this is the single source of truth. **Changing
`backend/config.py` changes the dashboard with no frontend edit.**

### `Survivor`

One confirmed person at their latest known position.

```python
track_id, latitude, longitude, confidence,
first_frame, confirmed_frame, last_frame, detection_count,
priority, priority_band, cluster_size, cluster_score
```

Two fields repay attention:

**`confirmed_frame`** — when this track *earned* its place, not when it first
appeared. The dashboard filters on this. A track first seen at frame 100 and
confirmed at 160 is not a survivor at frame 130.

**`cluster_score: Optional[float]`** — `None` means the term came out identical
for every survivor and was **dropped**, not that nobody is nearby. `cluster_size`
still says how many are. The dashboard can then honestly say "cluster size did
not differentiate on this clip" rather than printing a confident 0.00.

Note the docstring's careful distinction between two exclusions:

- An **untracked** detection (`track_id == -1`) has no identity to accumulate
  evidence against — it cannot be de-duplicated at all.
- A **short** track has an identity; the evidence for it was too thin.

Different reasons, and keeping them apart is what lets the dashboard explain
each.

### `MissionEvent`

One thing that happened, at the frame it happened on. **Only two kinds cross this
boundary** — `cluster_formed` and `priority_band` — because only these two need
server-side maths to derive.

Replay start, first detections, the closing summary are *not* here. The frontend
derives those from the survivor roster it already holds, so the log's
confirmation lines **are** the header's survivor count rather than a second tally
that has to agree with it.

---

## 5. `backend/tracks.py` — the persistence rule

93 lines, one job: **which track IDs are confirmed survivors, and when.**

It exists as its own module for one reason: `/api/survivors` and `backend/events`
both need this rule, and if each implemented it, they could implement it
*differently*. One module, one rule, no possibility of divergence.

### `min_track_frames()`

```python
def min_track_frames() -> int:
    return max(1, config.MIN_TRACK_FRAMES)
```

The floor, explained in Part 3. `int()` truncation at low frame rates could
produce 0, and `frames[0 - 1]` reads the *last* element — confirming every track
at the frame it was last seen. A silent, plausible-looking inversion. Flooring at
1 makes the degenerate case a no-op.

### `confirmation_frames(detections)`

```python
frames_by_track: Dict[int, Set[int]] = {}
for detection in detections:
    if detection.track_id < 0:
        continue
    frames_by_track.setdefault(detection.track_id, set()).add(detection.frame_id)

threshold = min_track_frames()
confirmed: Dict[int, int] = {}
for track_id, frames in frames_by_track.items():
    if len(frames) < threshold:
        continue
    ordered = sorted(frames)
    confirmed[track_id] = ordered[threshold - 1]
return confirmed
```

**Returns:** `track_id → the frame its threshold-th detection landed on.**

Three deliberate details:

1. **A `set` of frames, not a count of records.** A tracker emits one box per
   track per frame, so on well-formed input they're identical — but the rule is
   written in *frames*, and a duplicated record should not buy a track a
   fractional second of persistence it did not earn.

2. **Unconfirmed tracks are absent entirely.** Membership of the returned mapping
   *is* the roster. A caller cannot check one thing and read another.

3. **`ordered[threshold - 1]`** — the threshold-th frame in ascending order. The
   instant the track had accumulated enough evidence.

---

## 6. `backend/localize.py` — pixel to GPS

214 lines, four functions. The maths is derived in Part 6; this is the code.

### `ground_sample_distance()`

```python
return 2.0 * altitude * math.tan(math.radians(fov) / 2.0) / width
```

Metres of ground per pixel. At your constants: **0.018 m/px**, about 1.8 cm.

### `origin_for_frame(frame_id)`

Where the drone is assumed to be when that frame was captured.

```python
distance_m = speed * (frame_id / rate)
bearing = math.radians(heading)
north_m = distance_m * math.cos(bearing)
east_m  = distance_m * math.sin(bearing)
```

**The heading convention is a trap and the docstring calls it out.** A compass
bearing is 0 = north, 90 = east, clockwise. That is *not* the mathematical
convention. So **north takes the cosine and east the sine** — the opposite way
round from the usual polar-to-cartesian pair.

Get it backwards and the track mirrors across the north-east diagonal, which
looks like a perfectly plausible flight either way. That is the dangerous kind of
bug: no crash, no error, just wrong.

### `pixel_to_latlon(x, y)`

```python
east_m  = (x - width / 2.0) * scale
north_m = (height / 2.0 - y) * scale   # y grows down, north grows up
```

**Note the sign flip on the northing.** Image *y* grows downward; latitude grows
northward. A pixel below the centre of the frame is **south** of the origin, so
its `dlat` must be negative.

The formula in `CONVENTIONS.md` is written in terms of a ground offset and leaves this
implicit. Getting it wrong mirrors every survivor across the drone's position —
again, plausible-looking and completely wrong.

*(You saw this class of bug live: "the waypoint for human detected on map was
outside park earlier, now I re-ran it's inside.")*

### `bbox_to_latlon(bbox, frame_id)`

The box **centre** is used. Under a nadir camera a person's footprint sits
directly beneath them, so the centre is the best single-point estimate. Under an
*oblique* view the bottom edge would be the ground-contact point — different
camera, different answer.

`frame_id` is **required, not optional**, because the answer genuinely depends on
it: the same pixel in frame 0 and frame 299 is 62 m apart on the ground at the
configured speed. A default would silently pick one.

### `bbox_to_reference_latlon(bbox)` — the important one

```python
CLUSTER_REFERENCE_FRAME: int = 0

def bbox_to_reference_latlon(bbox):
    return bbox_to_latlon(bbox, CLUSTER_REFERENCE_FRAME)
```

Three lines, and it fixes the worst bug in the priority system.

**The problem it solves:** `origin_for_frame` advances the origin along an
*assumed* track. That is right for an absolute position — a survivor last seen
forty frames ago was last seen somewhere the drone has since flown past.

But it makes the distance between two survivors depend on how far apart in
**time** their last sightings were. At 5 m/s, a three-second gap manufactures
**fifteen metres** of separation between two people who may have been standing
next to each other.

**What it cost:** track 1409, the highest-confidence detection in the entire clip
at 0.802, ranked **21st of 23**. Its only fault was being last seen ~3 s after
everyone else.

**The rule:**

> A **relative** measurement — how far apart are these people — must be taken at
> one reference frame.
> An **absolute** measurement — how far is this person from that hazard — keeps
> the real moving-origin position.

The choice of reference frame is arbitrary and does not affect any distance:
shifting every point by the same offset leaves the gaps between them unchanged.
What matters is that *one* frame is used for everybody.

---

## 7. `backend/priority.py` — the scoring formula

350 lines. **This module contains the arithmetic and no numbers** — every weight,
radius and threshold comes from `config`.

### The formula in one sentence

> A survivor's priority is a weighted average of how confident the detector is,
> how many other survivors are within 15 m of them, and how close the nearest
> known hazard is.

That sentence is the deliverable. A judge will ask, and "a neural network
decides" is a bad answer.

### `metres_between(lat1, lon1, lat2, lon2)`

Flat-earth distance. Same assumption as `localize`, appropriate for the same
reason: a clip covers a few dozen metres, where the difference from a proper
geodesic is far below the error already in a fixed-altitude pixel projection.

### `cluster_score(neighbours)`

```python
return min(neighbours / limit, 1.0)
```

Linear to `CLUSTER_SATURATION` (4), flat at 1.0 above.

### `hazard_score(lat, lon)`

```python
if not known:
    return None
return max(0.0, 1.0 - nearest / reach)
```

**Returns `None`, not `0.0`, when there are no hazards.** The docstring is
explicit: the caller must not substitute 0.0, because that claims a measurement
nobody made.

### `band_for(score, previous=None)` — hysteresis

```python
BANDS = ("low", "medium", "high", "critical")

raw = 0
for index, cut in enumerate(cuts):
    if score >= cut:
        raw = index + 1

if previous is None or previous not in BANDS:
    return BANDS[raw]

margin = config.BAND_HYSTERESIS
current = BANDS.index(previous)

while raw > current and score < cuts[raw - 1] + margin:
    raw -= 1
while raw < current and score >= cuts[raw] - margin:
    raw += 1

return BANDS[raw]
```

**The problem it solves:** the confidence term is the confidence of each track's
latest detection, and that jitters frame to frame. A track parked near a cut does
not sit there — it oscillates. The event log showed single tracks changing band
**five times in nine seconds**, which reads as an unstable assessment when what
is unstable is one bounding box's confidence.

**How it works:** with no `previous`, the raw thresholds decide — that is where a
survivor *starts*. With one, climbing needs `cut + margin` and falling needs
`cut - margin`.

**Two properties worth being able to state:**

1. **A genuine multi-band jump still lands in one step.** The margin is only
   checked against cuts *actually being crossed*, so a score that travels far
   moves the band the whole way immediately.
2. **It is idempotent.** `band_for(s, band_for(s, p)) == band_for(s, p)` —
   verified over a 1,000-point grid from every starting band. Re-scoring an
   unchanged score never moves anyone. This is what lets `/api/survivors` recover
   the log's closing bands by re-scoring rather than keeping a second copy of the
   walk's state.

**The visible consequence:** sorted by score, bands can look inverted — one
survivor at 0.274 in *low* above another at 0.264 in *medium*, because they
arrived from opposite directions. That is correct, and the dashboard explains it.

### `score_all(survivors, previous_bands, cluster_positions)`

The main entry point. Batch rather than per-survivor **because the cluster term
is not a property of one person** — it is how many others are near them. A single
survivor cannot be scored in isolation.

**Pass one** — count neighbours, compute cluster scores:

```python
for index, (latitude, longitude) in enumerate(geometry):
    neighbours = 0
    for other_index, (other_lat, other_lon) in enumerate(geometry):
        if other_index == index:
            continue
        if metres_between(...) <= config.CLUSTER_RADIUS_M:
            neighbours += 1
```

O(n²), and deliberately so: *n* is the number of distinct tracks in one clip,
which is tens. A spatial index would be more code to get wrong for no measurable
gain.

**The drop test:**

```python
cluster_differentiates = bool(cluster_scores) and min(cluster_scores) != max(cluster_scores)
```

Exact equality is correct here and is not a floating-point tolerance question:
these values all come out of the same expression over an integer count, so equal
counts give bit-identical scores.

**Pass two** — the weighted average:

```python
terms = [(config.WEIGHT_CONFIDENCE, confidence)]
if cluster is not None:
    terms.append((config.WEIGHT_CLUSTER_SIZE, cluster))
if hazard is not None:
    terms.append((config.WEIGHT_HAZARD_PROXIMITY, hazard))

total_weight = sum(weight for weight, _ in terms)
score = sum(weight * value for weight, value in terms) / total_weight
score = min(max(score, 0.0), 1.0)
```

**The renormalisation is the elegant part.** Weights are *relative* and divided
by their own sum. They need not add to 1, and dropping a term renormalises the
survivors rather than capping everyone below 1.

Concretely on your clip: with both cluster and hazard dropped, the formula is
`0.4 × confidence / 0.4` = **confidence**. Scores span the full 0.19–0.80 range
rather than being squashed into the top by a constant +0.43.

**The final clamp is defensive.** A weight typed negative in config would
otherwise put an out-of-range score into a Pydantic model and surface as a 500
from an apparently unrelated endpoint.

---

## 8. `backend/events.py` — the mission timeline

331 lines. Walks the clip once and produces two things: the event log, and the
band state it closes on.

### The two event kinds, and why only two

- `cluster_formed` — needs ground positions, so it needs `localize`
- `priority_band` — needs the scoring formula, so it needs `priority`

Everything else the log shows is derived in the frontend from state it already
holds. That is deliberate: it makes the log's confirmation lines **the same list**
as the header's survivor count.

### `_clusters()` — union-find

```python
parent = list(range(count))

def find(node):
    while parent[node] != node:
        parent[node] = parent[parent[node]]   # path halving
        node = parent[node]
    return node
```

**Single-linkage connected components.** If A is within 15 m of B and B within
15 m of C, all three are one cluster even if A and C are 30 m apart.

`find` walks up to a group's representative; `parent[node] = parent[parent[node]]`
is **path halving**, an optimisation that flattens the tree as it goes.

**A distinction to have ready:** a cluster (a whole connected group) and
`cluster_size` (one survivor's direct neighbour count) are **not the same number
and are not meant to be**. A chain of people 14 m apart is one cluster here and
two neighbours each in the table. Both statements are true.

### `_walk()` — the single pass

```python
for frame_id in frames:
    # update the running "latest detection per track" table
    # find new clusters
    # if due: re-score, emit band changes
```

**Why clusters check every frame and priority does not:** they are different
kinds of fact. A cluster membership is a *first occurrence* — each distinct set
fires once ever, so re-checking costs nothing and buys exact timing. A band is a
*state that can oscillate*, and re-checking every frame produced **277 changes**
on the development fixture, almost all of them noise.

Priority is therefore **sampled** every `EVENT_SAMPLE_INTERVAL_S` (1 second), with
two forced exceptions:

- **When a track is confirmed**, because adding someone to the roster is the one
  thing that provably moves every other survivor's cluster term
- **On the final frame**, so the log closes on the same assessment
  `/api/survivors` gives the table

**Two levers, not one.** Sampling sets how *often* the question is asked;
hysteresis sets how much evidence a different *answer* needs. Sampling alone
still reports a flip whenever two consecutive samples land on opposite sides of a
cut — which is exactly what the log showed. Both are disclosed on the dashboard.

### `final_bands()` — the reconciliation fix

`/api/survivors` scores a *single frame*. The event log *walked to* that frame.
With hysteresis, those give different answers: a survivor sitting at 0.763 would
be "critical" in the table and "high" in the log — **same person, two bands on
screen at once**, which is precisely the reconciliation failure `CONVENTIONS.md`'s
dashboard requirements open with.

So `final_bands()` exposes the walk's closing state, and the endpoint scores
against it. Because `band_for` is idempotent, re-scoring cannot drift.

Cost: 0.023 s on your clip. It is `O(frames × tracks²)` and the detections file is
re-read every request anyway, so if the clip gets much longer both want caching
together.

---

## 9. `backend/routing.py` — ground routes for the rescue team

The route on the map is the path a **team on foot** takes from the staging
point to a survivor. It is not the drone's flight path — `simulation/planners.py`
owns that one, and they are different problems with different costs. A drone
flies over a collapsed building; a team goes around it.

**A\* over a risk-weighted grid.** The search area becomes a grid of
`ROUTE_CELL_M` cells. Each cell carries a risk derived from its distance to the
nearest hazard, with the same linear decay `priority.py` uses:

```
risk(cell) = max(0, 1 - nearest_hazard_distance / HAZARD_INFLUENCE_M)
```

Step cost is distance × (1 + `ROUTE_HAZARD_WEIGHT` × risk), so a route will
happily walk further to stay out of a hazard's influence. Movement is
8-connected with √2 diagonals, and the heuristic is straight-line distance —
admissible, so A\* returns the true optimum.

**Two paths travel together on purpose.** `path` avoids risk; `direct_path`
ignores it. The gap between them is what the risk weighting bought, and it is
the only honest way to show that "safe route" means something — a single
polyline is just a line. When no hazards are known the two are identical, and
the API says `hazard_aware: false` rather than implying something was avoided.

**Start and goal are never blocked.** A survivor detected inside a hazard zone
is exactly the person the system exists to reach.

---

## 10. `backend/alerts.py` — what warranted interrupting somebody

Alerts are **derived**, never authored — from the event timeline and the
survivor roster. Only one field is not derived: `state`, read from a delivery
ledger on disk, because whether an alert reached anyone is a fact about the
world and cannot be recomputed from the clip.

Three rules fire:

| Rule | Fires when |
|---|---|
| `critical_survivor` | a survivor's band *transitions* into critical |
| `cluster` | a group reaches `ALERT_CLUSTER_MIN`, then each time it grows by `ALERT_CLUSTER_STEP` |
| `hazard_proximity` | a survivor is within `ALERT_HAZARD_M` of a known hazard |

**Why the cluster rule has a step.** Measured on the demo clip: without it, one
component accumulating members one at a time emitted **eighteen** alerts —
"group of 3", "group of 4", "group of 5", all the same people. An operator
interrupted eighteen times for one group has learned to ignore the nineteenth.
The step rule took it to eight. Same principle as the critical band: the
*transition* is the news, not the state.

**Three states, kept strictly apart.** `queued` means nobody has tried.
`sent` means a channel accepted it. `failed` means a channel **refused**.
Collapsing `failed` into `queued` would let a broken webhook hide behind "we're
offline anyway", which is the one failure an alerting system must never conceal.

**Delivery is priority-ordered and idempotent.** The flush drains highest
priority first — bandwidth allocation mirroring rescue ranking — and an
append-only JSONL ledger with last-write-wins on read means a second flush
re-sends nothing. It ships with no channel configured, so the dashboard reads
"*N* queued — no channel configured", which is the offline claim demonstrated
rather than asserted.

---

## 11. `backend/main.py` — the routes

### The endpoints

| Route | Returns |
|---|---|
| `GET /api/health` | Liveness, for the connection indicator |
| `GET /api/config` | Every constant, as one object |
| `GET /api/detections` | Every raw detection record |
| `GET /api/events` | The mission timeline |
| `GET /api/survivors` | Confirmed survivors, ranked |
| `GET /tiles/{z}/{x}/{y}.png` | One cached map tile |

### `_load_detections()`

Read from disk **per request**, not cached at startup. The file is a few hundred
KB, and re-running the model shows up immediately instead of needing a restart.

Both `/api/detections` and `/api/survivors` go through here, so the counts they
imply come from **one read of one file** and cannot disagree.

Error handling distinguishes three states: missing file (503, with the command to
produce it), invalid JSON (500), and success.

### `GET /tiles/{z}/{x}/{y}.png`

Serves cached OpenStreetMap tiles from disk, so the base map survives a dead
venue network.

**On path traversal:** `z`, `x` and `y` are typed as `int`, so FastAPI rejects
anything that is not a bare integer *before the function runs*. No separator can
reach the filesystem. That is a nice illustration of type annotations doing
security work.

### `GET /api/survivors` — the full request lifecycle

This is the endpoint worth being able to trace end to end.

```
1. _load_detections()
     → reads detections.json, validates every record against Detection

2. tracks.confirmation_frames(records)
     → 333 track IDs in, 23 confirmed out, each with its confirmation frame

3. loop over records
     → skip track_id < 0        (no identity)
     → skip unconfirmed         (evidence too thin)
     → accumulate: latest detection, first frame, detection count

4. for each confirmed track:
     localize.bbox_to_latlon(bbox, frame_id)        → the real position (map, hazards)
     localize.bbox_to_reference_latlon(bbox)        → the relative geometry (clusters)

5. events_module.final_bands(records)
     → walks the whole clip to recover each track's current band

6. priority.score_all(positions, previous_bands, cluster_geometry)
     → neighbour counts, term-drop test, weighted average, band with hysteresis

7. build Survivor objects, sort by (-priority, track_id)

8. FastAPI validates each against the Survivor schema and serialises to JSON
```

**Step 4 is the subtle one.** Two positions are computed per survivor, from the
same box, in different reference frames, for different questions. Absolute for the
map and hazards; reference-frame for cluster distance.

**The sort key is `(-priority, track_id)`.** The negation sorts descending;
`track_id` breaks ties so equal scores keep a fixed order rather than shuffling
between requests, which on a polling dashboard would look like the ranking
changing on its own.

---

## 12. The call graph

```
main.py
  ├── config          (everything reads this)
  ├── schemas         (Detection, Survivor, ClipConfig, MissionEvent, Health)
  ├── tracks ─────────► config
  ├── localize ───────► config
  ├── priority ───────► config, localize (METRES_PER_DEGREE_LAT)
  └── events ─────────► config, localize, priority, tracks
```

**No cycles.** `config` depends on nothing. `localize` and `tracks` depend only on
config. `priority` adds localize. `events` composes all four. `main` wires them to
HTTP.

That layering is why you can test `localize` without starting a server, and why
Robin can develop `priority.py` without touching anything else.

---

## What to take from this part

- FastAPI + uvicorn + Pydantic. Type annotations do validation, not decoration.
- **`config.py` holds every number so that a judge's question has one place to go.**
- `tracks.py` exists so the persistence rule cannot be implemented twice
  differently.
- `localize.py` has two projections on purpose: absolute for position, reference-
  frame for relative distance.
- `priority.py` renormalises weights, so a dropped term redistributes rather than
  caps.
- `events.py` walks once and yields both the log and the band state, which is what
  makes the log and the table agree **by construction** rather than by luck.

**Next:** Part 6 derives the mathematics — GSD, the 111,320 constant, the priority
weights, and the clustering.

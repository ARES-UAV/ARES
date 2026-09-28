# Part 6 — The Mathematics, Derived

Every formula in ARES, worked out from first principles with your actual
constants substituted in. Nothing here is asserted; you should be able to
reproduce each result on paper.

---

## 1. Ground Sample Distance

### The question

You have a photograph taken from directly above. How many metres of real ground
does one pixel of that photograph cover?

### The derivation

The camera has a **field of view** — the angular width of what it can see. Call it
`FOV`. The camera is at altitude `H`, pointing straight down (**nadir**).

Draw the triangle. The camera is the apex. The ground is the base. The FOV angle
is split evenly by the vertical line down to the ground directly beneath, so each
half is `FOV/2`.

```
              camera
                /|\
               / | \
   FOV/2 →    /  |  \    ← FOV/2
             /   H   \
            /    |    \
    ───────┴─────┴─────┴───────  ground
           ← half → ← half →
             W/2       W/2
```

In the right triangle formed by the vertical drop and one half of the ground
width:

```
tan(FOV/2) = opposite / adjacent = (W/2) / H
```

Rearranging:

```
W/2 = H · tan(FOV/2)

W = 2 · H · tan(FOV/2)
```

That is the **ground footprint** — the real-world width the frame covers.

Divide by the number of pixels across that width and you have metres per pixel:

```
GSD = 2 · H · tan(FOV/2) / image_width
```

### With your numbers

```
H            = 20 m
FOV          = 60°
image_width  = 1280 px

tan(30°)     = 0.577350

W   = 2 × 20 × 0.577350 = 23.094 m
GSD = 23.094 / 1280      = 0.018042 m/px
```

**Every pixel is 1.8 centimetres of ground.**

The frame is 1280 × 720, so it covers **23.09 m × 12.99 m** of ground — about the
footprint of a tennis court.

You can verify this against the API: `ground_footprint_m` in `/api/config` is
`23.094010767585026`. That is not a typed constant — `main.py` computes it as
`localize.ground_sample_distance() * config.FRAME_WIDTH`, from the same function
the survivor positions come out of. The footprint the panel shows and the
footprint the pins were placed with are arithmetically one number.

### Why pixels are assumed square

`FOV` here is the **horizontal** field of view, pairing with the image width. The
code assumes square pixels, which makes the same GSD apply vertically. That is
true for essentially every modern sensor.

---

## 2. Pixel offset to ground offset

The drone is directly above `(origin_lat, origin_lon)`, looking down. **The centre
pixel of the frame is that coordinate.** Everything else is an offset from it.

```
east_m  = (x - width/2)  × GSD
north_m = (height/2 - y) × GSD
```

### The sign flip — the important part

Look carefully at the two lines. They are not symmetric.

- **East:** `x - width/2`. A pixel to the *right* of centre gives a positive
  number, and right is east. Straightforward.
- **North:** `height/2 - y`. Reversed.

Why? **Image coordinates put `y = 0` at the top and grow downward.** Latitude
grows *northward*. So a pixel *below* the centre of the frame — a larger `y` — is
**south** of the origin, and its northing must be negative.

Writing `y - height/2` would mirror every survivor across the drone's position.
The map would still look plausible. Every position would be wrong.

The formula in `CONVENTIONS.md` is written in terms of a generic ground offset and
leaves this flip implicit, which is exactly why `localize.py`'s docstring calls it
out explicitly.

### Worked example

A detection with its box centre at pixel `(900, 200)`:

```
east_m  = (900 - 640) × 0.018042 = 260 × 0.018042 =  4.69 m
north_m = (360 - 200) × 0.018042 = 160 × 0.018042 =  2.89 m
```

**4.69 m east and 2.89 m north** of whatever the drone was above at that frame.

---

## 3. Metres to degrees

### Latitude — the 111,320 constant

Lines of latitude are (approximately) evenly spaced. Going one degree north moves
you the same distance whether you start at the equator or at 60°N.

That distance is the Earth's circumference divided by 360:

```
WGS84 equatorial radius  R = 6,378,137 m
circumference            C = 2πR = 40,075,017 m
one degree               C/360 = 111,319.5 m
```

Hence `METRES_PER_DEGREE_LAT = 111_320.0`.

**An honest footnote.** The Earth is an oblate spheroid, so the *meridional*
degree is not quite constant — it runs from about 110,574 m at the equator to
111,694 m at the poles. At your latitude of 26.4° it is roughly 110,795 m, so
111,320 overestimates by about **0.47%**.

Over a 23 m frame, 0.47% is **11 centimetres**. That is far below the error
already present from assuming a fixed altitude and flat terrain. The
approximation is fine, and knowing *why* it is fine — rather than not knowing it
is an approximation at all — is the difference worth having.

### Longitude — why it needs a cosine

Lines of longitude **converge at the poles**. At the equator a degree of longitude
is ~111 km; at the North Pole it is zero.

The scale factor is the cosine of the latitude:

```
metres_per_degree_lon = 111,320 × cos(latitude)
```

At your origin latitude of 26.405892°:

```
cos(26.405892°) = 0.89565
111,320 × 0.89565 = 99,703 m per degree of longitude
```

So at Tezpur, a degree of longitude is about **10% shorter** than a degree of
latitude.

### Putting it together

```
Δlat = north_m / 111,320
Δlon = east_m  / (111,320 × cos(lat0))

lat = lat0 + Δlat
lon = lon0 + Δlon
```

Continuing the worked example, from origin `(26.405892, 92.233479)`:

```
Δlat = 2.89 / 111,320  = 0.0000260°
Δlon = 4.69 / 99,703   = 0.0000470°

lat = 26.405918
lon = 92.233526
```

---

## 4. The flight track

The drone does not hover. At 20 m altitude the camera sees 23 m of ground, so a
**stationary** origin would put every survivor in the clip inside one 23 m square
regardless of how long the drone flew. That is not what a search flight looks
like, and it makes the map unreadable.

There is no telemetry to read a real track from, so one is assumed: a straight
line at constant speed and heading from frame 0.

```
t        = frame_id / fps            seconds since frame 0
distance = speed × t                 metres along the heading
```

### The heading convention — the second trap

```python
north_m = distance_m * math.cos(bearing)
east_m  = distance_m * math.sin(bearing)
```

**North takes the cosine. East takes the sine.** That is the opposite of the
mathematical polar-to-cartesian convention you learned in school, where `x = r
cos θ` and `y = r sin θ`.

The reason: a **compass bearing** measures clockwise from north, whereas a
mathematical angle measures anticlockwise from east. They are reflections of each
other.

Getting this backwards mirrors the track across the north-east diagonal — and at
a heading of 45°, which is what your config uses, **it produces exactly the same
answer**. The bug would be invisible on this clip and appear the moment anyone
changed the heading. Worth knowing.

### Worked example

At frame 240, 24 fps, 5 m/s, heading 45°:

```
t        = 240 / 24 = 10 s
distance = 5 × 10   = 50 m

north_m = 50 × cos(45°) = 35.36 m
east_m  = 50 × sin(45°) = 35.36 m

Δlat = 35.36 / 111,320 = 0.000318°
Δlon = 35.36 / 99,703  = 0.000355°
```

The drone has moved 50 m north-east from where it started.

---

## 5. Why the cluster term needs a different reference frame

This is the most interesting piece of mathematics in the project, because it is a
case where the *right* model for one question is the *wrong* model for another.

### The problem, stated formally

Survivor *i* was last seen at frame *fᵢ*. Their absolute position is:

```
Pᵢ = O(fᵢ) + δᵢ
```

where `O(f)` is the drone's assumed origin at frame *f*, and `δᵢ` is the pixel
offset converted to metres.

Now take the distance between two survivors:

```
|Pᵢ - Pⱼ| = |O(fᵢ) - O(fⱼ) + δᵢ - δⱼ|
```

The term `O(fᵢ) - O(fⱼ)` is **the drone's movement between their two last
sightings.** It has nothing to do with how far apart the two people are.

At 5 m/s, a three-second gap contributes:

```
5 × 3 = 15 metres
```

**Fifteen metres of separation manufactured out of nothing but a timing
difference.**

### The fix

Localize every survivor against one fixed reference frame `f₀`:

```
Qᵢ = O(f₀) + δᵢ
```

Then:

```
|Qᵢ - Qⱼ| = |O(f₀) - O(f₀) + δᵢ - δⱼ| = |δᵢ - δⱼ|
```

**The origin term cancels exactly.** The distance depends only on the pixel
offsets, which is the only spatial relationship this clip actually observed.

Note that the *choice* of `f₀` is irrelevant — shifting every point by the same
vector leaves all pairwise distances unchanged. What matters is that **one** frame
is used for everybody. `CLUSTER_REFERENCE_FRAME = 0` is arbitrary and correct.

### The measured impact

| | moving origin | single reference frame |
|---|---|---|
| Apparent span of 23 survivors | 38.26 m | **11.38 m** |
| Cluster sizes | 1, 6, 9, 11, 17–21 | 22 for every survivor |
| Track 1409's rank | 21st of 23 | **1st** |

### The rule

> A **relative** measurement uses one reference frame.
> An **absolute** measurement uses the real, moving origin.

The hazard term deliberately keeps the moving origin, because a hazard has a fixed
ground position and the distance to it is an absolute question.

---

## 6. The priority formula

### The weighted average

```
        w_c · C  +  w_l · L  +  w_h · H
score = ───────────────────────────────
              w_c + w_l + w_h
```

| Symbol | Term | Weight |
|---|---|---|
| `C` | Detection confidence, 0–1 | `w_c = 0.4` |
| `L` | Cluster (neighbour count, normalised) | `w_l = 0.3` |
| `H` | Hazard proximity | `w_h = 0.3` |

### Why divide by the weight sum

Because it makes the weights **relative rather than absolute**, and that is what
lets a term be dropped cleanly.

With all three present, the denominator is 1.0 and the division does nothing.
The moment a term is dropped, it matters enormously.

### The cluster term

```
L = min(neighbours / CLUSTER_SATURATION, 1.0)      # saturation = 4
```

| Neighbours | L |
|---|---|
| 0 | 0.00 |
| 1 | 0.25 |
| 2 | 0.50 |
| 3 | 0.75 |
| 4+ | 1.00 |

**Why a ceiling.** Without one, a group of twenty would give `L = 5.0` for its
members, and normalising against the maximum would crush every other survivor's
cluster term toward zero. Beyond four neighbours the distinction stops carrying
information — five together and nine together are both "a crowd."

### The hazard term

```
H = max(0, 1 - distance / HAZARD_INFLUENCE_M)      # influence = 50 m
```

Linear falloff: 1.0 at the hazard itself, 0.0 at 50 m and beyond.

**Currently `None`, not `0.0`,** because `HAZARDS` is empty. A zero would read as
"checked, nothing nearby" — a claim nobody measured.

### The term-drop rule, worked

**All three terms present:**

```
score = (0.4·C + 0.3·L + 0.3·H) / 1.0
```

**Hazard dropped** (no classifier yet):

```
score = (0.4·C + 0.3·L) / 0.7
      = 0.5714·C + 0.4286·L
```

**Both dropped** (the current clip — cluster uniform):

```
score = 0.4·C / 0.4 = C
```

**The score becomes exactly the detection confidence.** That is what a single
renormalised term means, and it is why `priority` equals `confidence` in your API
output.

### Why dropping beats keeping-at-a-constant

When the cluster term is uniform at `L = 1.0` for everybody, keeping it gives:

```
score = 0.5714·C + 0.4286 × 1.0
      = 0.5714·C + 0.4286
```

A **flat +0.4286 added to every survivor.** It changes no ordering — but it lifts
the entire scene into "high" and "critical" and makes a uniform crowd read as a
uniformly severe one. Your clip read **16 high / 7 critical with nothing below.**

Dropping it restores the full 0.19–0.80 range and the ramp starts discriminating
again: 1 critical / 9 high / 10 medium / 3 low.

### Verify it yourself — two real survivors

**Track 1409**, before the reference-frame fix: `C = 0.80`, 1 neighbour so
`L = 0.25`, hazard dropped.

```
score = (0.4 × 0.80 + 0.3 × 0.25) / 0.7
      = (0.320 + 0.075) / 0.7
      = 0.395 / 0.7
      = 0.564
```

The API reported **0.565**. ✓ (the difference is rounding on the stored
confidence)

**Track 1314**, same run: `C = 0.67`, 17 neighbours so `L = min(17/4, 1) = 1.0`.

```
score = (0.4 × 0.67 + 0.3 × 1.0) / 0.7
      = (0.268 + 0.300) / 0.7
      = 0.568 / 0.7
      = 0.811
```

The API reported **0.813**. ✓

**After the fix**, both have 22 neighbours, the term is uniform and dropped, and
each score becomes its own confidence: 1409 → 0.802, first place.

That arithmetic is worth being able to do on a whiteboard. It is the most
convincing possible demonstration that you know what your own system computes.

---

## 7. Band thresholds and hysteresis

### The cuts

```
low      [0.00, 0.25)
medium   [0.25, 0.50)
high     [0.50, 0.75)
critical [0.75, 1.00]
```

**The quarters of the range.** That is the whole rule. They are deliberately not
fitted to the current clip's distribution — thresholds tuned to make a demo
colourful are the same failure as fabricated data.

### Hysteresis as a state machine

A band is not a one-off verdict; it is a **state that gets re-read**. And the
confidence term jitters frame to frame, so a track parked near a cut does not sit
there — it oscillates.

With `BAND_HYSTERESIS = h = 0.03`, each cut becomes a **deadband**:

```
        high                    critical
  ────────────────┬───┬────────────────────
                0.72 0.78
                  └─┬─┘
              deadband, width 2h

  climbing to critical:  needs score ≥ 0.75 + 0.03 = 0.78
  falling back to high:  needs score <  0.75 - 0.03 = 0.72
  in between:            hold whatever band you already had
```

**A score can legitimately sit past a printed threshold in the band below.** That
is the case the dashboard's `HysteresisNote` explains on screen, and it is the
one a judge is most likely to notice.

### Two properties

**Multi-band jumps still land in one step.** The margin is only checked against
cuts *actually being crossed*:

```python
while raw > current and score < cuts[raw - 1] + margin:
    raw -= 1
```

The loop stops at `current`, so a genuine escalation from `low` to `critical`
moves the whole way immediately.

**Idempotence.** `band_for(s, band_for(s, p)) == band_for(s, p)` — verified over a
1,000-point grid from every starting band. Re-scoring an unchanged score never
moves anyone. This is precisely what lets `/api/survivors` recover the log's
closing bands by re-scoring rather than storing a second copy of the walk's
state.

### The measured effect

| | before | after |
|---|---|---|
| Band assessments | 58 | 45 |
| Actual band changes | 35 | 22 |
| Worst single track | 6 changes | 3 |

And in the current run: **46 `priority_band` events = 23 initial assignments (one
per survivor) + 23 real changes.** One re-band per person across the whole clip.
`from_band` never contains `critical`, meaning nobody ever left it — the band a
judge scrutinises hardest is the one that never moves.

---

## 8. Clustering — union-find

### The algorithm

**Single-linkage connected components.** Two survivors are linked if they are
within `CLUSTER_RADIUS_M`; a cluster is a connected component of that graph.

Union-find (disjoint-set) maintains the components:

```python
parent = list(range(n))          # each node starts as its own group

def find(node):                   # which group is this in?
    while parent[node] != node:
        parent[node] = parent[parent[node]]   # path halving
        node = parent[node]
    return node

# union: link every pair within range
for i in range(n):
    for j in range(i + 1, n):
        if distance(i, j) <= radius:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj
```

**Path halving** — `parent[node] = parent[parent[node]]` — flattens the tree while
walking it. Combined with union, this gives near-constant amortised lookup
(inverse-Ackermann, which is under 5 for any conceivable input).

### Transitivity, and why it is not a bug

Single-linkage is **transitive**: A near B, B near C means A, B, C are one cluster
even if A and C are 30 m apart.

That is the correct semantics for "one rescue trip serves this group" — you walk
the chain. But it means a radius comparable to the scene size merges everything.

On your clip the question is settled by measurement rather than argument: **max
pairwise separation is 11.38 m against a 15 m radius.** Every survivor is directly
within range of every other. That is a *complete graph* — chaining cannot be what
is happening, because there are no intermediate links to chain through. One
cluster is the literal truth.

### Cluster vs `cluster_size` — not the same number

- A **cluster** is the whole connected component.
- **`cluster_size`** is one survivor's *direct* neighbour count.

A chain of people 14 m apart is one cluster and two neighbours each. Both
statements are true, and the code documents the distinction deliberately.

Note also: `cluster_size = 22` for a group of **23** — it excludes self. The
dashboard must therefore say "22 **others** within 15 m", or the two numbers read
as a contradiction.

### Complexity

O(n²) for the pairwise pass, in both `priority.score_all` and `events._clusters`.
Deliberate: *n* is the number of distinct tracks in one clip, which is tens. A
k-d tree or spatial hash would be more code to get wrong for no measurable gain.

---

## 9. How accurate is any of this?

The honest error budget, which is a genuinely good thing to have ready.

| Source | Effect on relative position over an 11 m span |
|---|---|
| Altitude assumed 20 m, actually ±10% | ±1.1 m |
| Terrain relief ±2 m | ±1.1 m |
| **Camera tilt 5° off nadir** | **~1.75 m shift — and this row is the one that grows, see §10** |
| Box centre estimate, ±3 px | ±0.05 m |
| Flat-earth vs geodesic | ~0.001 m |
| 111,320 vs true meridional degree | ~0.11 m |

**Total: roughly one to two metres of uncertainty on relative positions.**

Two conclusions follow, and both are worth stating:

1. **The approximations are not the problem.** Flat-earth and the constant
   latitude degree contribute millimetres. The assumed altitude and attitude
   dominate by three orders of magnitude. Replacing the projection with a proper
   geodesic would be pure theatre.

2. **You cannot honestly resolve sub-3-metre structure.** Splitting an 11 m group
   into 3 m sub-groups claims about three times the resolution the method has.
   That is the principled reason `CLUSTER_RADIUS_M` stays at 15.

The accuracy this buys is **"good enough to put a pin on the right building"**,
not survey grade. `localize.py`'s docstring says exactly that, and so should the
pitch.

---

## 10. The nadir assumption, and what it actually costs

§9's table prices camera tilt at 5°, which is what a hovering aircraft holding
station might drift to. That is the gentle case, and it hides the real one.

**A multirotor translates only by tilting.** There is no other way for it to
produce horizontal thrust. So for as long as the aircraft is moving between
search cells — which is most of a sortie — the camera is not at nadir, and the
whole projection in §2 is being applied to a frame it does not describe.

The error is a bearing error, not a scale error, and it is `H·tan θ`:

| Airframe tilt | Shift at H = 20 m | Share of the 23.09 m footprint |
|---|---:|---:|
| 5° | 1.75 m | 7.6 % |
| 10° | 3.53 m | 15.3 % |
| **20°** | **7.28 m** | **31.5 %** |
| 30° | 11.55 m | 50.0 % |

At 20° every pin moves **7.3 m** — about half of `CLUSTER_RADIUS_M`. Read §5
and §8 again with that number in mind: a 7 m displacement can merge two
connected components or split one, group size is a scored term in §6, and the
ranking changes. **The error does not stop at the coordinate. It reaches the
order the dashboard tells you to rescue people in.**

Altitude error is negligible beside it. GSD is linear in `H`, so a 0.4 m
excursion is a 2 % scale error — 0.46 m across the entire frame. **Tilt is the
term worth engineering against; height hold is not.**

### Where the angles come from

A quadcopter PID study on Swift Pico in MuJoCo — a 1.525 kg airframe, 21.88 N
of maximum thrust, hover at 68.4 % of it, and no aerodynamic damping at all.
That study measured altitude leaving its tolerance band precisely while pitch
and roll were making their large corrections, and put the thrust cost of
tilting at `T·cos θ` — 6 % at 20°, 13 % at 30°, against a margin of only 32 %
above hover.

Different airframe, different simulator. Treat the **angles** as the right
order of magnitude rather than as ARES's own numbers; the **displacement
arithmetic** above is exact for any airframe.

### What follows

IMU fusion is not a checklist item on the roadmap. It is worth about seven
metres of localization error, and that is the honest reason to build it. Two
mitigations need no new sensor and belong in the flight plan rather than in
`localize.py`:

- **Capture level.** Hold attitude while observing, translate between
  observations. Costs search time, removes the error.
- **Gate on attitude.** Tag each frame with its tilt and drop detections above
  a threshold. Costs coverage, removes the error.

**This does not correct the current demo, and cannot.** Those pins come from
stored VisDrone and C2A footage whose true camera attitude is unknown, so the
nadir assumption is undischarged in both directions — it is not that the
footage is nadir and only a real flight would differ.

---

## What to take from this part

- `GSD = 2H·tan(FOV/2)/width`. Yours is 1.8 cm/px, footprint 23.09 × 12.99 m.
- **The northing sign flips** because image *y* grows down and latitude grows up.
- 111,320 m per degree of latitude; multiply by `cos(lat)` for longitude.
- **The origin term cancels exactly** when relative distance is measured at one
  reference frame — that is the proof behind `bbox_to_reference_latlon`.
- Renormalising by the weight sum is what makes a dropped term redistribute
  rather than cap. With both dropped, `score = confidence`.
- You can verify the formula by hand: 1409 → 0.564, 1314 → 0.811. Both match.
- Hysteresis makes each cut a 2h-wide deadband, and it is idempotent.
- Error is 1–2 m and dominated by the assumed altitude, not by the maths.

**Next:** Part 7 — the frontend, from "what is React" through every component.

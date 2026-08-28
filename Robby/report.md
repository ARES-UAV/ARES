# ARES — Robin's Contribution Report

**Project:** ARES-UAV
**Contributor:** Robin
**Contribution Area:** Survivor Detection Reliability, Localization, Priority Scoring & Tracker Evaluation
**Platform:** Rescue UAV / Search-and-Rescue Dashboard
**Report Version:** 1.0
**Date:** 28 August 2026

---

## 1. Executive Summary

This report documents Robin's contribution to the ARES rescue UAV project.

The objective of this contribution is to make the existing survivor-detection pipeline more suitable for search-and-rescue operations by improving:

* survivor representation
* detection reliability
* spatial localization
* localization consistency
* priority explainability
* survivor grouping
* tracker evaluation
* operator-facing information

The implementation deliberately preserves the project's existing architectural decisions around persistence filtering, relative reference-frame geometry, priority-score renormalization, and hysteresis.

The central engineering principle is:

> A rescue UAV should communicate not only where a survivor may be, but also how reliable that information is and why that survivor has been prioritized.

No fabricated detections, hazards, medical conditions, or benchmark results are introduced.

---

# 2. Existing ARES System

ARES processes precomputed UAV detection data through a backend pipeline before presenting survivor information to an operator.

The high-level pipeline is:

```text
Detection Data
      ↓
Tracking
      ↓
Persistence Filtering
      ↓
Confirmed Survivors
      ↓
Localization
      ↓
Spatial Clustering
      ↓
Priority Scoring
      ↓
FastAPI
      ↓
Rescue Dashboard
```

The supplied project guide identifies the current demo characteristics as:

* 7,081 raw detections
* 333 tracker IDs
* 23 confirmed survivors
* 24 FPS footage
* 20 m UAV altitude
* 60° nadir FOV
* 1280 × 720 video
* 5 m/s UAV speed
* 045° bearing
* 2.5-second persistence requirement

These values are configuration-dependent and should not be treated as universal system limits.

---

# 3. Robin's Assigned Scope

Robin's assigned work covers:

1. localization
2. priority scoring
3. score explainability
4. survivor position consistency
5. survivor grouping
6. tracker evaluation
7. rescue-oriented detection reliability

The project guide explicitly identifies `backend/localize.py` and `backend/priority.py` as Robin's primary modules.

The existing persistence filtering and clustering infrastructure should be reused rather than unnecessarily rewritten.

---

# 4. Problem Statement

A rescue UAV operates under difficult conditions:

* small people in aerial imagery
* partial occlusion
* detector confidence fluctuations
* moving-camera geometry
* tracker fragmentation
* imperfect position estimates
* limited operator attention
* incomplete environmental information

A system that only outputs a bounding box is therefore insufficient.

The rescue operator needs to know:

```text
Who?
Where?
How reliable?
Which group?
What priority?
Why?
```

The contribution addresses these questions while maintaining transparent system behavior.

---

# 5. Survivor Detection Reliability

## 5.1 Existing Challenge

The detection threshold is intentionally recall-oriented.

The demo configuration uses a relatively low detection confidence threshold.

This allows more person-like objects to enter the tracking stage, but it also creates:

* false positives
* short-lived tracks
* detector flicker
* fragmented identities

The project guide reports that short tracks tend to have lower confidence than long-lived tracks.

Therefore, the system should not interpret every raw detection as a confirmed survivor.

---

## 5.2 Persistence-Based Confirmation

ARES uses persistence as a confirmation gate.

The configured requirement is:

```text
MIN_TRACK_SECONDS = 2.5
```

The number of frames is derived from the actual frame rate.

Conceptually:

```python
MIN_TRACK_FRAMES = max(
    1,
    int(MIN_TRACK_SECONDS * CLIP_FPS)
)
```

This makes the system portable across different camera frame rates.

This distinction is important because:

```text
2.5 seconds at 24 FPS = 60 frames
2.5 seconds at 1.5 FPS ≈ 3 frames
```

A fixed frame threshold would therefore behave incorrectly when the camera frame rate changes.

---

# 6. Localization Improvements

## 6.1 Ground Projection

ARES estimates ground position from the UAV camera using nadir projection.

At the configured:

```text
Altitude = 20 m
FOV = 60°
Image width = 1280 px
```

the expected ground sampling distance is approximately:

```text
0.018 m/pixel
```

with an approximate ground footprint of:

```text
23.09 m
```

This is an engineering approximation rather than survey-grade geolocation.

---

## 6.2 Absolute vs Relative Geometry

Two localization operations are intentionally kept separate.

### Absolute location

```text
bbox_to_latlon(bbox, frame_id)
```

is used for:

* survivor map position
* absolute geographic location
* hazard distance
* position estimates

### Relative location

```text
bbox_to_reference_latlon(bbox)
```

is used for:

* survivor-to-survivor distance
* clustering
* group membership
* relative geometry

This separation prevents temporal differences between detections from becoming artificial spatial distances.

---

# 7. Median Survivor Position

The previous approach relied on the last available position estimate.

This can make the displayed position sensitive to one erroneous bounding box.

The improved implementation uses the median of valid position estimates:

```python
latitude = median(all_latitudes)
longitude = median(all_longitudes)
```

The median was selected because it is resistant to individual outliers.

This is particularly useful for aerial detection because one inaccurate bounding box can move the estimated ground position significantly.

---

# 8. Localization Spread

Each survivor now exposes:

```text
position_spread_m
```

This is calculated as the maximum distance between the representative median position and any individual position estimate.

Conceptually:

```python
position_spread_m = max(
    metres_between(
        median_latitude,
        median_longitude,
        estimate_latitude,
        estimate_longitude
    )
)
```

### Interpretation

A small value indicates that the survivor's estimated position is spatially consistent.

A large value indicates that the detection geometry varies significantly and that the operator should treat the displayed location with greater caution.

This value is intentionally described as **position spread**, not absolute GPS accuracy.

It is an internal consistency metric.

---

# 9. Priority Scoring

ARES uses an explainable weighted scoring model.

The conceptual weights are:

| Signal               | Weight |
| -------------------- | -----: |
| Detection confidence |    0.4 |
| Spatial cluster      |    0.3 |
| Hazard proximity     |    0.3 |

The important implementation rule is that unavailable or non-discriminative signals are dropped rather than assigned zero.

---

## 9.1 Why Dropping Matters

If a signal is unavailable, assigning it zero would imply:

> "The system measured this signal and determined it was zero."

That is different from:

> "The system did not measure this signal."

ARES therefore omits unavailable signals and renormalizes the remaining weights.

For example, if hazard information is unavailable:

```text
score = (0.4 × confidence + 0.3 × cluster) / 0.7
```

If both cluster and hazard terms are unavailable:

```text
score = confidence
```

This keeps the score mathematically honest.

---

# 10. Score Breakdown

Each survivor now exposes the contribution of each scoring signal.

Example:

```json
{
  "confidence": 0.3208,
  "cluster": 0.2100
}
```

If hazard information is unavailable, the hazard field is omitted.

It is not represented as:

```json
"hazard": 0
```

This distinction is important for operator trust.

The breakdown must satisfy:

```text
sum(weighted contributions) ≈ final priority
```

within the configured numerical tolerance.

---

# 11. Priority Hysteresis

Priority bands use hysteresis to prevent unstable switching caused by confidence fluctuations.

Without hysteresis, a survivor near a priority boundary could rapidly alternate between:

```text
HIGH
MEDIUM
HIGH
MEDIUM
```

even though the underlying person has not meaningfully changed.

The hysteresis mechanism therefore improves operator stability.

The implementation must preserve:

* threshold behavior
* hysteresis
* idempotence
* consistency between survivor and event APIs

---

# 12. Survivor Grouping

ARES already contains connected-component clustering.

Robin's contribution exposes that grouping information directly to survivors.

New fields:

```text
group_id
group_size
```

### Important distinction

`cluster_size`:

> direct neighbours excluding the survivor

`group_size`:

> all members of the connected component including the survivor

Therefore:

```text
cluster_size = 22
group_size = 23
```

can both be correct.

---

# 13. Rescue Operator Benefits

Group information helps an operator recognize situations such as:

```text
Group A
23 survivors
```

rather than treating every survivor as an unrelated target.

This can support:

* rescue-team allocation
* search-area planning
* prioritization of dense survivor locations
* situational awareness

The system does not infer that group members are necessarily physically dependent on one another.

It only reports the spatial grouping calculated by the clustering algorithm.

---

# 14. Tracker Evaluation

The project contains tooling for comparing tracking approaches.

The evaluation should compare ByteTrack and BoT-SORT using identical detections.

Important metrics include:

* unique IDs
* highest ID issued
* identity fragmentation
* identity switches
* persistence behavior
* survivor confirmation consistency

The purpose is not to select the tracker with the most aesthetically pleasing output.

The relevant question is:

> Which tracker provides more reliable survivor identities under rescue-search conditions?

---

# 15. Detection/Tracking Benchmark

OpenCode must populate this section using actual experiment results.

| Metric                | Before | After | Difference |
| --------------------- | -----: | ----: | ---------: |
| Raw detections        |    TBD |   TBD |        TBD |
| Tracker IDs           |    TBD |   TBD |        TBD |
| Confirmed survivors   |    TBD |   TBD |        TBD |
| False-positive tracks |    TBD |   TBD |        TBD |
| Identity switches     |    TBD |   TBD |        TBD |
| Position spread       |    TBD |   TBD |        TBD |

**Important:** Never replace `TBD` with invented numbers.

If an experiment cannot be performed, state why.

---

# 16. Localization Validation

Localization should be tested using known geometric expectations.

## Tests

### Center pixel

The frame center should correspond to the UAV ground position for the reference frame.

### Image direction

```text
Top    → North
Bottom → South
Left   → West
Right  → East
```

### Drone movement

The difference between frame positions should correspond to:

```text
speed × elapsed time
```

along the configured bearing.

### Heading convention

Compass heading is:

```text
0°   = North
90°  = East
180° = South
270° = West
```

The implementation must use compass-bearing mathematics rather than conventional mathematical-angle assumptions.

---

# 17. Testing

The implementation should include tests for:

## Localization

* GSD calculation
* frame-center position
* north/south direction
* east/west direction
* heading
* moving UAV
* median location
* position spread

## Priority

* all signals available
* hazard unavailable
* cluster unavailable
* both unavailable
* weight renormalization
* score breakdown
* dropped-term omission
* hysteresis
* idempotence

## Groups

* isolated survivor
* multiple groups
* connected chains
* group-size semantics
* cluster-size semantics
* deterministic group IDs

## API

* backwards-compatible fields
* new fields
* valid JSON
* `/api/survivors`
* `/api/events`

---

# 18. Rescue UAV Suitability

The resulting system is intended to support rescue operations through four principles.

## 18.1 Reliability

Only persistent tracks should become confirmed survivors.

## 18.2 Spatial Consistency

Multiple observations are summarized using a robust representative position and a spread metric.

## 18.3 Explainability

Priority scores expose their contributing signals.

## 18.4 Graceful Degradation

Unavailable information is explicitly reported rather than fabricated.

For example:

```text
Hazard: Not scored
```

is preferable to:

```text
Hazard: 0
```

when no hazard classifier exists.

---

# 19. Operator-Facing Information

A survivor card should ideally communicate:

```text
SURVIVOR #1409

Priority: CRITICAL
Score: 0.802

Confidence: 0.802

Location:
26.xxxxx, 92.xxxxx

Position spread:
X.X m

Group:
A · XX survivors
```

If a score component is unavailable:

```text
Hazard
Not scored
```

rather than:

```text
Hazard
0
```

The operator should be able to understand the result without reading source code.

---

# 20. API Changes

Existing fields must remain compatible.

Existing:

```text
track_id
latitude
longitude
confidence
first_frame
confirmed_frame
last_frame
detection_count
priority
priority_band
cluster_size
cluster_score
```

New:

```text
position_spread_m
score_breakdown
group_id
group_size
```

No existing field should be silently renamed.

In particular:

```text
latitude
longitude
```

must remain the API field names.

---

# 21. Files Changed

OpenCode must populate this table after implementation.

| File                  | Change | Reason                    |
| --------------------- | ------ | ------------------------- |
| `backend/localize.py` | TBD    | Localization improvements |
| `backend/priority.py` | TBD    | Explainable priority      |
| `backend/events.py`   | TBD    | Group information         |
| `backend/...`         | TBD    | TBD                       |
| `frontend/...`        | TBD    | Rescue operator UI        |
| `tests/...`           | TBD    | Regression coverage       |

Only include files actually modified.

---

# 22. Before/After Behavior

## Before

The system primarily communicates:

```text
Survivor
Location
Confidence
Priority
```

## After

The system communicates:

```text
Survivor
Location
Localization consistency
Confidence
Priority
Priority explanation
Group membership
Group size
```

This changes the dashboard from a simple detection display into a more operationally useful rescue-assistance interface.

---

# 23. Limitations

The system is not a replacement for:

* human rescue teams
* professional GPS systems
* survey-grade mapping
* medical assessment
* certified disaster-response systems

Localization accuracy depends on assumptions including:

* UAV altitude
* camera FOV
* camera orientation
* UAV heading
* flat-ground approximation
* detection bounding-box quality

Position spread indicates internal consistency; it does not constitute certified geolocation accuracy.

---

# 24. Safety and Reliability Considerations

The system should avoid presenting uncertain information as fact.

Important examples:

```text
Unknown hazard
```

should not become:

```text
No hazard
```

and:

```text
High localization spread
```

should not become:

```text
Accurate location
```

Likewise, a high detection confidence should not be interpreted as proof that a person is medically safe, injured, conscious, or otherwise in a particular condition.

The system detects and prioritizes visual targets.

It does not perform medical diagnosis.

---

# 25. Reproducibility

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

Test survivor endpoint:

```bash
curl -s localhost:8000/api/survivors
```

Start frontend:

```bash
cd frontend
npm install
npm run dev
```

The required demo detection/video assets must be present in their expected locations.

---

# 26. Verification Checklist

* [ ] Backend starts successfully
* [ ] `/api/survivors` works
* [ ] `/api/events` works
* [ ] Existing API fields remain compatible
* [ ] `score_breakdown` is present
* [ ] Score breakdown sums to priority
* [ ] Dropped terms are absent
* [ ] Median position is used
* [ ] `position_spread_m` is present
* [ ] Group IDs are deterministic
* [ ] `group_size` includes the survivor
* [ ] `cluster_size` excludes the survivor
* [ ] Localization tests pass
* [ ] Priority tests pass
* [ ] Hysteresis tests pass
* [ ] Frontend still loads
* [ ] Map still renders
* [ ] Video still works
* [ ] Tracker evaluation completed or documented as unavailable
* [ ] No fabricated benchmark values
* [ ] No unrelated files modified
* [ ] `.venv`, datasets, videos and weights are not committed

---

# 27. Final Results

OpenCode must complete this section after implementation.

## Implementation Summary

```text
TBD
```

## Detection Reliability

```text
TBD
```

## Localization

```text
TBD
```

## Priority Scoring

```text
TBD
```

## Group Detection

```text
TBD
```

## Tracker Evaluation

```text
TBD
```

## Dashboard

```text
TBD
```

---

# 28. Engineering Conclusion

Robin's contribution strengthens ARES by turning raw visual detections into more useful rescue information.

The key improvements are:

```text
Raw detections
      ↓
Reliable survivor confirmation
      ↓
Robust location estimate
      ↓
Localization consistency
      ↓
Spatial grouping
      ↓
Explainable priority
      ↓
Operator-ready rescue information
```

The design deliberately favors transparency over artificial sophistication.

The system should never create a more impressive-looking result by inventing information.

For rescue UAV applications, an honest:

> "Hazard not scored"

or:

> "Position spread is high"

is more valuable than a precise-looking number with no measurement behind it.

---

# 29. Final Contribution Statement

Robin's contribution focuses on making ARES more operationally credible for aerial search-and-rescue by improving the reliability, spatial consistency, explainability, and presentation of survivor detections.

The contribution does not attempt to replace the detection model or turn the system into an opaque end-to-end AI.

Instead, it strengthens the existing pipeline with measurable and explainable engineering improvements.

**Final status:** To be completed after implementation and testing.

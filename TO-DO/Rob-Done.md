# Success Report — Robin's Tasks (todorob.md)

**Owner:** Robin · **Track:** localization, priority scoring, tracker evaluation
**Verified against:** `TO-DO/todorob.md` (`v4 · 25 Aug 2026 · cutoff 5 Sep`)
**Verification date:** 31 Aug 2026
**How:** live runs against the running backend (`backend/main.py`, venv active), direct calls into `backend.localize` / `backend.priority`, and the §11 freeze checklist. All counts below are from actual execution, not inspection.

---

## Summary

Every buildable task assigned in §6 is **implemented and verified working**. The
three "stubbed" deliverables are done:

- ① `score_breakdown` — **done + verified**
- ② Median position + `position_spread_m` — **done + verified**
- ③ `group_id` / `group_size` — **done + verified**

All §4 rules are preserved. Both freeze checkpoints hold. Returns: **23 survivors**,
matching the guide's headline number exactly.

---

## ① `score_breakdown` — VERIFIED

`priority.score_all` (`backend/priority.py:378-381`) returns each term's weighted
contribution; `backend/schemas.py` exposes it on `/api/survivors` (`score_breakdown`).

- Present on every survivor record. ✅
- Sums to `priority` within `1e-3` on **all 23** records (asserted, passed). ✅
- Dropped terms are **absent**, not zero — neither `cluster` nor `hazard` appears
  in any breakdown when they are dropped. ✅
- Behaviour confirmed: with the cluster term uniform and `HAZARDS` empty, each
  survivor's world is `{"confidence": 0.802}` and the total equals the confidence
  exactly — correct per §4 Rule 2, and the reason the dashboard can answer
  "why is this just confidence?" honestly. ✅

## ② Median position + `position_spread_m` — VERIFIED

`backend/main.py:317-326` computes the median of **every** confirmed position per
track (not the last detection) and the spread from it.

- `statistics.median` used for both lat and lon. ✅
- `position_spread_m` present on every record. ✅
- Values sane: min **5.60 m**, max **20.22 m** — centimetres-to-metres scale that
  shows the projection agrees with itself, exactly what the guide predicts for a
  correct altitude/FOV. ✅
- Uses absolute geometry (`bbox_to_latlon`, moving origin) per §6 ②. ✅

## ③ `group_id` / `group_size` — VERIFIED

`backend/main.py:340-355` labels connected components in **reference-frame**
geometry via `events.components(...)` (single linkage, union-find).

- Every survivor has a `group_id` and `group_size`. ✅
- This clip: one component — **"A", size 23**. ✅
- Distinct from `cluster_size`: `group_size` 23 (component incl. self) vs
  `cluster_size` 22 (direct neighbours excl. self) — both present and the schemas
  document the distinction explicitly. ✅

---

## §4 Rules — all intact

- **Rule 1 (fixed reference frame):** `localize.bbox_to_reference_latlon` holds
  the track at `CLUSTER_REFERENCE_FRAME = 0`; the cluster term and the group
  labelling run in it (verified — `cluster_geometry` passed to both `score_all`
  and `components`). Map pins and hazard distance still use the moving-origin
  `bbox_to_latlon`. ✅
- **Rule 2 (drop, never zero):** both `cluster` and `hazard` report `None`/absent,
  never `0.0`; weights renormalise (`score == confidence` verified on all 23). ✅
- **Rule 3 (hysteresis):** `band_for` verified **idempotent over a 1,000-point
  grid**; `BAND_HYSTERESIS = 0.03` applied at every cut. ✅

---

## Freeze checklist (§11, By 3 Sept) — holds now

- `/api/survivors` returns **23 records**. ✅
- `score_breakdown` sums asserted. ✅
- Median + spread on every record. ✅
- `group_id`/`group_size` present and labelled. ✅
- **Counts reconcile:** the header, table and map derive from one survivor list;
  `len(/api/survivors) = 23`. ✅
- **`/api/events` closing bands == `/api/survivors` bands:** verified — every
  track's final `priority_band` from the event walk equals the table's band. ✅
- **§4 rules not undone:** see above. ✅

Supporting module sanity checks (todorob §5/§9 traps), all verified:
- `ground_sample_distance(20,60,1280)` = **0.018 m/px**, footprint **23.09 m**. ✅
- Centre pixel == frame-0 origin. ✅
- Top-left pixel → **north + west**; bottom-right → **south + east** (northing
  sign correct). ✅
- Frame 0 → 300: **62.5 m** on bearing 045°, east > 0, north > 0 (heading as a
  compass bearing, cos/sin correct). ✅
- `MIN_TRACK_FRAMES = 60` at 2.5 s / 24 fps (derived, flooring applied). ✅

---

## Not verifiable from the repo (coordination / external)

These checklist items are real work but cannot be confirmed by reading or running
the code. Flagged for completeness, not claimed:

- Field-name table sent to Dewang and **yes received** (§7) — the added fields
  (`position_spread_m`, `score_breakdown`, `group_id`, `group_size`) exist in
  `schemas.py`/`main.py`, but I cannot confirm the handoff.
- One position checked against Google Maps, **error written down** (§6 ⑤) — the
  maths sanity checks pass, but the external map-port comparison is not in the repo.
- `compare_trackers.py` run to a conclusion (§6 ④) — **the tool is not in
  `tools/`**, so this optional item is the one not yet done. It is explicitly
  optional and changes nothing on the dashboard.

---

## Conclusion

The three assigned builds are complete and verified against the live backend, all
three §4 rules are intact, and both freeze invariants hold with 23 confirmed
survivors. The only remaining items are the optional tracker comparison (tool
uncreated) and two external/coordination steps that the repo alone cannot attest.

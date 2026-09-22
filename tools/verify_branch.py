#!/usr/bin/env python3
"""
Acceptance tests for a branch before it is merged.

    uvicorn backend.main:app --port 8000     # on the branch under test
    python tools/verify_branch.py

Exit 0 = safe to merge. Non-zero = do not merge, read the failures.

WHAT THIS IS FOR
    A contributor's own report says what they built. This says whether the
    dashboard still works. Those are different questions, and only the second
    one decides a merge.

    So the checks below split in two:

      CLAIMS      the things the branch says it added
      REGRESSION  the things it must not have broken — field names the
                  frontend reads, sort order it relies on, config keys it
                  renders, the data contract all three of us share

    The regression half matters more. A missing feature is visible. A renamed
    field silently blanks a panel.

WHY THE PROJECTION CHECK IS IN HERE
    §6② of the guide asks for `position_spread_m` and predicts it will read in
    centimetres if the geometry is right. It does not — it reads 5-20 m — and
    the reason is not a bug in anyone's code. See `check_projection`.
"""

from __future__ import annotations

import json
import statistics as st
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

BASE = "http://localhost:8000"

# Every field the frontend reads off a survivor record. Renaming any of these
# blanks a panel with no error anywhere — see the guide's §7.
REQUIRED_SURVIVOR_FIELDS = [
    "track_id", "latitude", "longitude", "confidence",
    "first_frame", "confirmed_frame", "last_frame", "detection_count",
    "priority", "priority_band", "cluster_size", "cluster_score",
]

# Every key /api/config must carry. The frontend renders from these and falls
# back to config.js only when the whole endpoint fails, not per-key.
REQUIRED_CONFIG_KEYS = [
    "clip_fps", "source_width", "source_height", "confidence_threshold",
    "detection_imgsz", "altitude_m", "camera_fov_deg", "origin_lat",
    "origin_lon", "drone_speed_ms", "drone_heading_deg", "ground_footprint_m",
    "device_fps", "device_name", "weight_confidence", "weight_cluster_size",
    "weight_hazard_proximity", "cluster_radius_m", "hazard_count",
    "band_hysteresis", "event_sample_interval_s", "min_track_seconds",
    "min_track_frames", "priority_medium_at", "priority_high_at",
    "priority_critical_at",
]

PASS, FAIL, WARN = [], [], []


def ok(msg): PASS.append(msg); print(f"  \033[32mPASS\033[0m  {msg}")
def bad(msg): FAIL.append(msg); print(f"  \033[31mFAIL\033[0m  {msg}")
def warn(msg): WARN.append(msg); print(f"  \033[33mWARN\033[0m  {msg}")


def get(path):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=20) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"\nBackend unreachable at {BASE}{path} — {e}\n"
                 f"Start it on the branch under test:\n"
                 f"  uvicorn backend.main:app --port 8000\n")


# ══════════════════════════════════════════════════════════════════════
#  REGRESSION — what must not have broken
# ══════════════════════════════════════════════════════════════════════

def check_contract(survivors, config, detections):
    print("\n── regression · the contract ──────────────────────────")

    missing = [f for f in REQUIRED_SURVIVOR_FIELDS if f not in (survivors[0] or {})]
    if missing:
        bad(f"survivor fields removed or renamed: {missing}")
    else:
        ok(f"all {len(REQUIRED_SURVIVOR_FIELDS)} survivor fields present")

    absent = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if absent:
        bad(f"/api/config keys missing: {absent}")
    else:
        ok(f"all {len(REQUIRED_CONFIG_KEYS)} config keys present")

    # The detection contract is shared by all three of us — CONVENTIONS.md.
    d = detections[0]
    expected = {"frame_id", "bbox", "confidence", "track_id", "class"}
    if set(d) != expected:
        bad(f"detection contract changed: {sorted(set(d))} != {sorted(expected)}")
    elif len(d["bbox"]) != 4:
        bad(f"bbox is not 4 values: {d['bbox']}")
    else:
        ok("detection JSON contract unchanged")

    # main.py guarantees this order and the dashboard renders it as the rescue
    # queue without re-sorting.
    keys = [(-s["priority"], s["track_id"]) for s in survivors]
    if keys != sorted(keys):
        bad("/api/survivors not sorted by priority desc, track_id asc")
    else:
        ok("survivors sorted by priority desc, ties by track_id")

    # Every survivor must be reachable by the frontend's progressive reveal,
    # which filters on confirmed_frame.
    if any(s.get("confirmed_frame") is None for s in survivors):
        bad("some survivors have no confirmed_frame — progressive reveal breaks")
    else:
        ok("every survivor has confirmed_frame")


def check_reconcile(survivors, events):
    print("\n── regression · counts reconcile ──────────────────────")
    ok(f"/api/survivors returns {len(survivors)} records")

    # The dashboard's header, table and map all render this one list, so the
    # only way they can disagree is if the list has duplicates.
    ids = [s["track_id"] for s in survivors]
    if len(set(ids)) != len(ids):
        bad("duplicate track_id in /api/survivors — header and table WILL disagree")
    else:
        ok("no duplicate track_ids")

    # The band in the table must equal the band the event log closes on.
    final = {}
    for e in events:
        if e.get("kind") == "priority_band" and e.get("track_id") is not None:
            final[e["track_id"]] = e.get("to_band")
    mismatch = [(s["track_id"], s["priority_band"], final[s["track_id"]])
                for s in survivors
                if s["track_id"] in final and final[s["track_id"]] != s["priority_band"]]
    if mismatch:
        bad(f"table band != event log closing band for {len(mismatch)}: {mismatch[:4]}")
    elif not final:
        warn("no priority_band events to cross-check")
    else:
        ok(f"table bands match event log closing bands ({len(final)} checked)")


# ══════════════════════════════════════════════════════════════════════
#  CLAIMS — what the branch says it added
# ══════════════════════════════════════════════════════════════════════

def check_breakdown(survivors):
    print("\n── claim ① score_breakdown ────────────────────────────")
    if "score_breakdown" not in survivors[0]:
        bad("score_breakdown absent"); return

    missing = [s["track_id"] for s in survivors if not s.get("score_breakdown")]
    if missing:
        bad(f"score_breakdown empty on {len(missing)} records")
    else:
        ok("score_breakdown on every record")

    off = [(s["track_id"], round(sum(s["score_breakdown"].values()), 4), s["priority"])
           for s in survivors
           if abs(sum(s["score_breakdown"].values()) - s["priority"]) >= 1e-3]
    if off:
        bad(f"breakdown does not sum to priority on {len(off)}: {off[:3]}")
    else:
        ok(f"breakdown sums to priority within 1e-3 on all {len(survivors)}")

    # A dropped term must be ABSENT. Present-at-zero reintroduces exactly the
    # false impression the drop rule exists to prevent.
    zeroed = [(s["track_id"], k) for s in survivors
              for k, v in s["score_breakdown"].items() if v == 0]
    if zeroed:
        bad(f"dropped terms present at 0.0 rather than absent: {zeroed[:4]}")
    else:
        ok("no term present at zero — dropped terms are absent")


def check_spread(survivors):
    print("\n── claim ② median position + position_spread_m ────────")
    if "position_spread_m" not in survivors[0]:
        bad("position_spread_m absent"); return
    vals = [s["position_spread_m"] for s in survivors]
    if any(v is None for v in vals):
        bad("position_spread_m null on some records"); return
    ok(f"position_spread_m on every record "
       f"(min {min(vals):.2f}, median {st.median(vals):.2f}, max {max(vals):.2f} m)")
    if max(vals) > 40:
        bad(f"spread reaches {max(vals):.1f} m — the guide's threshold for "
            f"a wrong altitude or frame width")


def check_groups(survivors):
    print("\n── claim ③ group_id / group_size ──────────────────────")
    for f in ("group_id", "group_size"):
        if f not in survivors[0]:
            bad(f"{f} absent"); return
    if any(s.get("group_id") is None for s in survivors):
        bad("group_id null on some records"); return

    sizes = {}
    for s in survivors:
        sizes.setdefault(s["group_id"], []).append(s["track_id"])
    ok(f"{len(sizes)} group(s): " +
       ", ".join(f"{g}={len(m)}" for g, m in sorted(sizes.items())))

    wrong = [(s["track_id"], s["group_size"], len(sizes[s["group_id"]]))
             for s in survivors if s["group_size"] != len(sizes[s["group_id"]])]
    if wrong:
        bad(f"group_size disagrees with actual membership: {wrong[:3]}")
    else:
        ok("group_size equals actual membership (self included)")

    # 22 vs 23 must be explainable, not a contradiction: cluster excludes self,
    # group includes it.
    s0 = survivors[0]
    if s0.get("cluster_size") is not None and s0["group_size"] == s0["cluster_size"]:
        warn("group_size == cluster_size — one of them is counting self wrongly")
    else:
        ok(f"group_size {s0['group_size']} vs cluster_size {s0['cluster_size']} "
           f"— differ as documented")


# ══════════════════════════════════════════════════════════════════════
#  The geometry, and what position_spread_m actually measures
# ══════════════════════════════════════════════════════════════════════

def check_projection(survivors=None):
    """Prove the projection is sane, and show what spread is really measuring.

    §6② predicts `position_spread_m` reads in centimetres if the maths agrees
    with itself. It reads 5-20 m. That is not a coding error — it is that the
    metric is computed with the MOVING origin, which advances along an ASSUMED
    5 m/s flight track. Over a track's lifetime that assumption dominates.

    The check that isolates the geometry is frame-to-frame displacement in the
    FIXED reference frame, where the assumed track cancels. If the projection
    is right, consecutive estimates land about one pixel of ground apart.
    """
    print("\n── the projection itself ──────────────────────────────")
    from backend import config as C, localize, tracks
    from backend.priority import metres_between
    from backend.schemas import Detection

    gsd = localize.ground_sample_distance()
    fp = gsd * C.FRAME_WIDTH
    if abs(gsd - 0.018) < 0.0005 and abs(fp - 23.09) < 0.1:
        ok(f"GSD {gsd*100:.2f} cm/px · footprint {fp:.2f} m")
    else:
        bad(f"GSD {gsd*100:.2f} cm/px, footprint {fp:.2f} m — expected 1.80 / 23.09")

    lat, lon = localize.pixel_to_latlon(C.FRAME_WIDTH / 2, C.FRAME_HEIGHT / 2)
    if abs(lat - C.ORIGIN_LAT) < 1e-9 and abs(lon - C.ORIGIN_LON) < 1e-9:
        ok("centre pixel at frame 0 == origin exactly")
    else:
        bad(f"centre pixel != origin: {lat}, {lon}")

    tl = localize.pixel_to_latlon(0, 0)
    br = localize.pixel_to_latlon(C.FRAME_WIDTH, C.FRAME_HEIGHT)
    if tl[0] > C.ORIGIN_LAT and tl[1] < C.ORIGIN_LON and br[0] < C.ORIGIN_LAT:
        ok("top-left is north+west, bottom-right south+east — northing sign correct")
    else:
        bad(f"northing/easting sign wrong: TL {tl}, BR {br}")

    path = C.DETECTIONS_PATH
    if not path.exists():
        warn("no detections.json — skipping the displacement check"); return
    recs = [Detection.model_validate(r) for r in json.loads(path.read_text())]
    conf = tracks.confirmation_frames(recs)
    by = {}
    for d in recs:
        if d.track_id in conf:
            by.setdefault(d.track_id, []).append(d)

    def steps(project):
        out = []
        for ds in by.values():
            ds.sort(key=lambda d: d.frame_id)
            for a, b in zip(ds, ds[1:]):
                if b.frame_id - a.frame_id == 1:
                    out.append(metres_between(*project(a), *project(b)))
        return out

    moving = st.median(steps(lambda d: localize.bbox_to_latlon(d.bbox, d.frame_id)))
    fixed = st.median(steps(lambda d: localize.bbox_to_reference_latlon(d.bbox)))
    per_frame = C.DRONE_SPEED_MS / C.CLIP_FPS

    print(f"\n        frame-to-frame displacement, same tracks:")
    print(f"          assumed drone travel  {per_frame*100:6.1f} cm/frame")
    print(f"          moving origin         {moving*100:6.1f} cm  "
          f"({moving*C.CLIP_FPS:.2f} m/s implied)")
    print(f"          fixed reference frame {fixed*100:6.1f} cm  "
          f"({fixed/gsd:.1f} px of box jitter)")

    if fixed < 3 * gsd:
        ok(f"fixed-frame jitter is {fixed/gsd:.1f} px — the projection agrees with itself")
    else:
        bad(f"fixed-frame jitter is {fixed/gsd:.1f} px — geometry may be wrong")

    # Which projection is position_spread_m actually using? Compare the API's
    # values against what each projection produces for the same tracks.
    if survivors:
        api_max = max(s_["position_spread_m"] for s_ in survivors
                      if s_.get("position_spread_m") is not None)
        ref_spread, mov_spread = [], []
        for ds in by.values():
            for proj, acc in (
                (lambda d: localize.bbox_to_reference_latlon(d.bbox), ref_spread),
                (lambda d: localize.bbox_to_latlon(d.bbox, d.frame_id), mov_spread),
            ):
                pts = [proj(d) for d in ds]
                mlat = st.median(p_[0] for p_ in pts)
                mlon = st.median(p_[1] for p_ in pts)
                acc.append(max(metres_between(mlat, mlon, *p_) for p_ in pts))

        if abs(api_max - max(ref_spread)) < abs(api_max - max(mov_spread)):
            ok(f"position_spread_m uses the fixed frame (max {api_max:.2f} m) — "
               f"it measures the projection")
        else:
            bad(f"position_spread_m uses the MOVING origin (max {api_max:.2f} m vs "
                f"{max(ref_spread):.2f} m fixed).\n"
                f"        It is measuring the assumed {C.DRONE_SPEED_MS} m/s flight "
                f"track, not the geometry — the\n"
                f"        distance between two estimates of ONE person is a relative "
                f"measurement, and Rule 1\n"
                f"        says those use the fixed frame. Run fix_position_spread.py.")


def main() -> None:
    print(f"\nVerifying the branch running at {BASE}")
    survivors = get("/api/survivors")
    if not survivors:
        sys.exit("/api/survivors returned nothing — is detections.json in place?")
    config = get("/api/config")
    events = get("/api/events")
    detections = get("/api/detections")

    check_contract(survivors, config, detections)
    check_reconcile(survivors, events)
    check_breakdown(survivors)
    check_spread(survivors)
    check_groups(survivors)
    check_projection(survivors)

    print("\n" + "=" * 62)
    print(f"  {len(PASS)} passed · {len(FAIL)} failed · {len(WARN)} warnings")
    print("=" * 62)
    if FAIL:
        print("\nDO NOT MERGE:")
        for f in FAIL:
            print(f"  · {f}")
    for w in WARN:
        print(f"\nnote: {w}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()

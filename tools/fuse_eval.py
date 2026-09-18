#!/usr/bin/env python3
"""
RGB-only vs thermal-only vs fused — the experiment the SIH plan asks for.

    python tools/fuse_eval.py --rgb rgb_preds.json --thermal ir_preds.json \\
                              --gt ground_truth.json

WHAT KIND OF FUSION THIS IS
    LATE fusion, at the decision level. Both detectors run independently on the
    same scene, their boxes are matched to each other, and the confidences are
    combined — which is exactly the formula in the plan document:

        C_fused = w_r * C_rgb + w_t * C_thermal        w_r + w_t = 1

    It is NOT early fusion (stacking RGB and thermal into a 4-channel input and
    training one network on it). Early fusion usually scores higher in papers.
    Late fusion is chosen here for three reasons that matter more than a point
    of mAP:

      1. It uses the two models we ALREADY HAVE. Early fusion means a new
         architecture and a new training run.
      2. It degrades gracefully. Lose the thermal camera in flight and the RGB
         detector keeps working — an early-fusion network handed a dead channel
         does something undefined.
      3. It is explainable. "Both sensors saw something here" is a sentence a
         judge can check. A learned 4-channel feature map is not.

THE UNMATCHED CASE, WHICH IS THE WHOLE POINT
    A detection seen by only one sensor gets the other's vote as ZERO:

        thermal only   C_fused = w_t * C_t
        RGB only       C_fused = w_r * C_r

    So single-sensor detections are penalised and agreements are rewarded.
    That is the mechanism by which fusion suppresses false positives — a hot
    car reads as a person to thermal alone, and RGB not confirming it drops it
    below threshold.

WHAT TO EXPECT, SO THE RESULT IS NOT OVERSOLD
    On a night-time dataset, thermal alone will beat RGB alone by a wide margin
    and fusion will land close to thermal. That is not a fusion result — it is
    a "thermal works in the dark" result, which nobody doubts.

    The honest headline is FALSE POSITIVES AT EQUAL RECALL. Fusion earns its
    place by removing detections one sensor believed and the other did not.
    That is what the summary below reports first.

INPUT FORMAT
    All three files are the team's detection contract, plus `image_id`:

        [{"image_id": "190001", "bbox": [x1,y1,x2,y2],
          "confidence": 0.87, "class": 0}, ...]

    Ground truth needs no confidence. Boxes must be in the SAME pixel space —
    LLVIP's pairs are registered, so this holds by construction. It does not
    hold for unregistered pairs, and fusing those is meaningless.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise IoU. a is (N,4), b is (M,4), both x1y1x2y2."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = ((a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]))[:, None]
    area_b = ((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]))[None, :]
    return inter / np.maximum(area_a + area_b - inter, 1e-9)


def by_image(records: list) -> dict:
    out = defaultdict(list)
    for r in records:
        out[str(r["image_id"])].append(r)
    return out


def fuse_one(rgb: list, thermal: list, w_r: float, w_t: float,
             match_iou: float) -> list:
    """Late-fuse one image's detections. Returns fused boxes with confidences.

    Greedy nearest-IoU matching. A matched pair contributes one box — the
    higher-confidence sensor's geometry, because thermal boxes are looser and
    RGB boxes are tighter, and taking the more confident one is a defensible
    rule that needs no extra parameter.
    """
    rb = np.array([d["bbox"] for d in rgb], dtype=float).reshape(-1, 4)
    tb = np.array([d["bbox"] for d in thermal], dtype=float).reshape(-1, 4)
    M = iou_matrix(rb, tb)

    used_r, used_t, fused = set(), set(), []
    # Highest IoU first, so a confident overlap is not stolen by a marginal one.
    for i, j in sorted(np.ndindex(M.shape), key=lambda p: -M[p]):
        if M[i, j] < match_iou:
            break
        if i in used_r or j in used_t:
            continue
        used_r.add(i); used_t.add(j)
        cr, ct = rgb[i]["confidence"], thermal[j]["confidence"]
        fused.append({
            "bbox": (rgb[i] if cr >= ct else thermal[j])["bbox"],
            "confidence": w_r * cr + w_t * ct,
            "agreed": True,
        })

    for i, d in enumerate(rgb):
        if i not in used_r:
            fused.append({"bbox": d["bbox"], "confidence": w_r * d["confidence"],
                          "agreed": False})
    for j, d in enumerate(thermal):
        if j not in used_t:
            fused.append({"bbox": d["bbox"], "confidence": w_t * d["confidence"],
                          "agreed": False})
    return fused


def evaluate(preds: dict, gt: dict, conf: float, match_iou: float) -> dict:
    """Precision / recall / F1 at one confidence threshold."""
    tp = fp = fn = 0
    for image_id, truths in gt.items():
        gb = np.array([g["bbox"] for g in truths], dtype=float).reshape(-1, 4)
        dets = [d for d in preds.get(image_id, []) if d["confidence"] >= conf]
        dets.sort(key=lambda d: -d["confidence"])
        db = np.array([d["bbox"] for d in dets], dtype=float).reshape(-1, 4)

        M = iou_matrix(db, gb)
        hit = set()
        for i in range(len(db)):
            j = int(np.argmax(M[i])) if M.shape[1] else -1
            if j >= 0 and M[i, j] >= match_iou and j not in hit:
                hit.add(j); tp += 1
            else:
                fp += 1
        fn += len(gb) - len(hit)

    p = tp / max(tp + fp, 1)
    r = tp / max(tp + fn, 1)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r,
            "f1": 2 * p * r / max(p + r, 1e-9)}


def at_equal_recall(preds: dict, gt: dict, target_recall: float,
                    match_iou: float) -> dict:
    """Sweep the threshold to hit `target_recall`, then report false positives.

    This is the comparison that means something. Two systems at different
    operating points cannot be compared on false positives directly — hold
    recall equal and the FP count becomes a fair number.
    """
    best = None
    for conf in np.arange(0.01, 1.0, 0.01):
        m = evaluate(preds, gt, float(conf), match_iou)
        if m["recall"] < target_recall:
            break
        best = dict(m, conf=float(conf))
    return best or {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rgb", type=Path, required=True)
    ap.add_argument("--thermal", type=Path, required=True)
    ap.add_argument("--gt", type=Path, required=True)
    ap.add_argument("--w-rgb", type=float, default=0.5,
                    help="w_r; w_t is 1 - w_r (default 0.5)")
    ap.add_argument("--match-iou", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=Path("experiments/fusion_result.json"))
    args = ap.parse_args()

    w_r = args.w_rgb
    w_t = 1.0 - w_r

    rgb = by_image(json.loads(args.rgb.read_text()))
    ir = by_image(json.loads(args.thermal.read_text()))
    gt = by_image(json.loads(args.gt.read_text()))

    fused = {img: fuse_one(rgb.get(img, []), ir.get(img, []), w_r, w_t,
                           args.match_iou)
             for img in gt}

    print(f"images {len(gt)}  ·  w_rgb {w_r}  w_thermal {w_t}  ·  "
          f"match IoU {args.match_iou}\n")

    systems = {"RGB only": rgb, "thermal only": ir, "FUSED": fused}

    print("At the F1-optimal threshold for each system")
    print(f"  {'':14}{'conf':>6}{'P':>8}{'R':>8}{'F1':>8}{'FP':>8}")
    best_conf, rows = {}, {}
    for name, preds in systems.items():
        cand = [dict(evaluate(preds, gt, float(c), args.match_iou), conf=float(c))
                for c in np.arange(0.05, 0.95, 0.05)]
        b = max(cand, key=lambda m: m["f1"])
        best_conf[name], rows[name] = b["conf"], b
        print(f"  {name:<14}{b['conf']:>6.2f}{b['precision']:>8.3f}"
              f"{b['recall']:>8.3f}{b['f1']:>8.3f}{b['fp']:>8}")

    # The comparison that actually tests fusion: hold recall equal, count FPs.
    target = min(rows[n]["recall"] for n in systems)
    print(f"\nAt EQUAL RECALL = {target:.3f} — the fair false-positive comparison")
    print(f"  {'':14}{'conf':>6}{'P':>8}{'R':>8}{'FP':>8}")
    eq = {}
    for name, preds in systems.items():
        m = at_equal_recall(preds, gt, target, args.match_iou)
        eq[name] = m
        if m:
            print(f"  {name:<14}{m['conf']:>6.2f}{m['precision']:>8.3f}"
                  f"{m['recall']:>8.3f}{m['fp']:>8}")

    if eq.get("FUSED") and eq.get("thermal only"):
        a, b = eq["FUSED"]["fp"], eq["thermal only"]["fp"]
        if b:
            print(f"\n  fusion vs best single sensor: {a} vs {b} false positives "
                  f"({100*(b-a)/b:+.1f}%)")

    agreed = sum(1 for v in fused.values() for d in v if d["agreed"])
    total = sum(len(v) for v in fused.values())
    print(f"\n  both sensors agreed on {agreed} of {total} fused detections "
          f"({100*agreed/max(total,1):.0f}%)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"w_rgb": w_r, "w_thermal": w_t, "match_iou": args.match_iou,
         "f1_optimal": rows, "equal_recall": eq,
         "agreement_rate": agreed / max(total, 1)}, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

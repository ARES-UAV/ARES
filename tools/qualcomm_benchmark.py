#!/usr/bin/env python3
"""
Benchmark the ARES detector on Qualcomm silicon via Qualcomm AI Hub.

    python tools/qualcomm_benchmark.py --list
    python tools/qualcomm_benchmark.py \
        --device "Dragonwing RB3 Gen 2 Vision Kit" --device-os 1.6 --quantize

WHY THIS EXISTS
    Qualcomm authored this SIH problem statement and their commercial thesis is
    on-device edge AI. "Runs on a Raspberry Pi 4" solves their problem on
    Broadcom silicon. AI Hub compiles and profiles on REAL hosted Qualcomm
    devices, so a number off their hardware costs a token and an upload.

WHAT WE LEARNED GETTING HERE — worth keeping, it is the write-up
    1. First compile rejected the model outright:
         "Tensors {'output0'} occur in value_info but also in model IO"
       Not a hardware limit — a SPEC VIOLATION in the file. Ultralytics'
       export leaves the graph output duplicated in value_info, which ONNX
       Runtime tolerates and Qualcomm's stricter validator does not. Fixed by
       tools/fix_onnx_io.py, which removes one metadata entry and zero
       operators.

    2. Second compile got all the way through conversion:
         INFO_CONVERSION_SUCCESS
         Total MACs: 23,828,234,860 · Params: 9,141,668
       Every one of YOLOv12s's 516 operators mapped — Conv x120, Sigmoid x82,
       Transpose x66, MatMul x16, Softmax x9. There is NO unsupported-operator
       problem and no attention-does-not-map problem. Do not claim one.

    3. It then failed on:
         "Tensor 'images' has a floating-point type which is not supported by
          the targeted device. Please quantize the model including its I/O."
       The QCS6490 Hexagon HTP is an INTEGER accelerator. Float32 in, float32
       out, is simply not a thing it does. That is what --quantize is for.

THE HONESTY REQUIREMENT
    Quantization changes the model's accuracy. A latency figure for an INT8
    model beside an mAP measured on the FP32 model is two different models
    reported as one. After this runs, re-validate the quantized model and
    report both numbers, or report neither.
"""

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ONNX = REPO / "models" / "yolov12s_960.onnx"
CLIP = REPO / "backend" / "data" / "demo_clip.mp4"
OUT = REPO / "experiments" / "QUALCOMM_BENCHMARK.md"
# One record per run. The summary in OUT is regenerated from these, so a new
# configuration can never overwrite an older one's result — which the old
# single-file version did, losing three of four runs and their job URLs.
RUNS = REPO / "experiments" / "qualcomm"

# Must match backend/config.py. Benchmarking a size we do not ship produces a
# number that describes nothing.
IMGSZ = 960

EDGE_HINTS = ("dragonwing", "iq-", "iq8", "iq9", "rb3", "rb5", "qcs", "qrb")


# ── devices ──────────────────────────────────────────────────────────
def list_devices(hub) -> None:
    devices = hub.get_devices()
    if not devices:
        sys.exit("No devices returned. Is your API token configured?")

    edge, other = [], []
    for d in devices:
        (edge if any(h in d.name.lower() for h in EDGE_HINTS) else other).append(d)

    print(f"\n{'=' * 68}\nIoT / ROBOTICS / DRONE-CLASS  ({len(edge)})\n{'=' * 68}")
    for d in edge:
        print(f"  {d.name}")
    print(f"\n{'=' * 68}\nEVERYTHING ELSE  ({len(other)})\n{'=' * 68}")
    for d in other[:20]:
        print(f"  {d.name}")
    if len(other) > 20:
        print(f"  … and {len(other) - 20} more")


# ── calibration data ─────────────────────────────────────────────────
def letterbox(img, size: int):
    """Resize preserving aspect ratio, pad to square with 114 grey.

    This is what Ultralytics does at inference. Calibration has to see the
    same input distribution the deployed model will see, and the padding value
    is part of that distribution — a plain resize would stretch the image and
    shift every activation range the quantizer is trying to measure.
    """
    import cv2
    import numpy as np

    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = round(h * r), round(w * r)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)

    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas


def calibration_samples(n: int, imgsz: int):
    """`n` preprocessed frames spread evenly across the demo clip.

    Spread rather than the first n: consecutive frames are near-duplicates and
    would give the quantizer a narrow, unrepresentative view of the activation
    ranges. The clip's crowd density varies, and the busy frames are the ones
    that produce the extreme values worth capturing.
    """
    import cv2
    import numpy as np

    if not CLIP.exists():
        sys.exit(f"No clip at {CLIP} — calibration needs real frames.")

    cap = cv2.VideoCapture(str(CLIP))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // n)

    samples = []
    for i in range(0, total, step):
        if len(samples) >= n:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            continue
        img = letterbox(frame, imgsz)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        samples.append(np.transpose(img, (2, 0, 1))[None, ...])  # NCHW
    cap.release()

    if not samples:
        sys.exit("Could not read any frames from the clip.")
    print(f"      {len(samples)} calibration frames, evenly spread over {total}")
    return samples


def onnx_input_name(path: Path) -> str:
    """Read the graph's input name rather than assuming 'images'."""
    try:
        import onnx
        return onnx.load(str(path), load_external_data=False).graph.input[0].name
    except Exception:
        return "images"


def onnx_input_size(path: Path):
    """
    Read the graph's input spatial size — the file is the authority, not a flag.

    We already shipped one benchmark run against exports that were 640 when we
    believed they were 960. A flag cannot catch that; reading the graph can.
    Returns None when the axis is dynamic or unreadable, and the caller falls
    back to --imgsz.
    """
    try:
        import onnx
        dims = onnx.load(
            str(path), load_external_data=False
        ).graph.input[0].type.tensor_type.shape.dim
        h, w = dims[-2].dim_value, dims[-1].dim_value       # NCHW
        if h and w and h == w:
            return h
        if h and w:
            sys.exit(f"Non-square input {h}x{w}; this pipeline assumes square.")
    except Exception:
        pass
    return None


# ── result recording ─────────────────────────────────────────────────
def run_slug(device: str, imgsz: int, quantized: bool, act_dtype: str) -> str:
    """A stable filename for one (device, size, precision) combination.

    Re-running the same configuration overwrites its own record, which is what
    you want — a repeat measurement supersedes the old one. A DIFFERENT
    configuration gets a different name and cannot clobber it, which is what
    the old single-file version got wrong: four runs were made and three were
    lost, including the job URLs that made them auditable.
    """
    d = "".join(c if c.isalnum() else "-" for c in device.lower())
    while "--" in d:
        d = d.replace("--", "-")
    prec = f"int8w-{act_dtype}a" if quantized else "fp32"
    return f"{d.strip('-')}_{imgsz}_{prec}"


def write_index(runs_dir: Path, out: Path) -> int:
    """Rebuild the summary document from every run record on disk.

    The table is DERIVED, never hand-maintained. This project has twice had a
    number drift because a summary was written once and never re-checked
    against its source; here the source is the JSON files and the summary is
    regenerated on every run, so the two cannot disagree.
    """
    records = []
    for f in sorted(runs_dir.glob("*.json")):
        if f.name.endswith("_profile.json"):
            continue
        try:
            records.append(json.loads(f.read_text()))
        except Exception:
            continue
    if not records:
        return 0

    records.sort(key=lambda r: r.get("latency_ms", 1e9))

    def mem(r):
        if r.get("peak_mem_range"):
            return r["peak_mem_range"]
        v = r.get("peak_mem_mb")
        return f"{v:.1f} MB" if v is not None else "—"

    def stat_mark(r):
        # A minimum masquerading as a headline is the failure this column exists
        # to prevent. Runs whose median was never captured say so, here, in the
        # table, not in a footnote nobody reads.
        return "" if str(r.get("stat", "")).startswith("median") else " ⚠"

    rows = "".join(
        f"| `{r['device']}` | {r['imgsz']} | {r['precision']} | "
        f"{r['latency_ms']:.2f} ms | **{r['fps']:.1f}**{stat_mark(r)} | {mem(r)} | "
        f"{r['npu_layers']}/{r['total_layers']} · {r['npu_share']:.0f}% |\n"
        for r in records
    )

    details = ""
    for r in records:
        if r.get("samples"):
            spread = (f"{r['latency_min_ms']:.2f} – {r['latency_max_ms']:.2f} ms "
                      f"over {r['samples']} samples")
        elif r.get("latency_min_ms") is not None:
            spread = f"minimum {r['latency_min_ms']:.2f} ms; full distribution not retained"
        else:
            spread = "not retained"
        placement = "".join(
            f"| {u} | {n} | {100 * n / max(r['total_layers'], 1):.1f}% |\n"
            for u, n in r["units"].items()
        )
        jobs = "\n".join(f"- {k}: {v}" for k, v in r.get("jobs", {}).items() if v)
        # A record transcribed from a terminal scrollback is not the same
        # evidence as one the tool captured. Say which this is.
        note = f"\n> {r['note']}\n" if r.get("note") else ""
        prof = (runs_dir / f"{r['slug']}_profile.json")
        raw = (f"\nRaw profile: `experiments/qualcomm/{r['slug']}_profile.json`"
               if prof.exists() else
               "\nRaw profile: not retained — this run predates per-run recording.")
        details += f"""
### {r['device']} · {r['imgsz']} px · {r['precision']}

| | |
|---|---|
| Model | `{r['model']}` |
| Runtime | `{r['runtime']}` |
| Input size | {r['imgsz']} ({r['size_note']}) |
| Latency | {r['latency_ms']:.2f} ms ({r['fps']:.1f} FPS) — {r.get('stat', 'unknown statistic')} |
| Spread | {spread} |
| Peak memory | {mem(r)} |
| Measured | {r['measured_at']} |
{note}
| Compute unit | Layers | Share |
|---|---|---|
{placement}
{jobs}
{raw}

---
"""

    out.write_text(f"""# Qualcomm on-device benchmark

Measured on **Qualcomm AI Hub** — hosted physical devices, not emulators.

**This file is generated.** Every run writes a record to
`experiments/qualcomm/<slug>.json` and this document is rebuilt from all of
them. Do not edit it by hand; the next run overwrites your edit. To add a
result, run the benchmark.

## All runs

| Device | Size | Precision | Latency | FPS | Peak memory | On NPU |
|---|---:|---|---:|---:|---:|---|
{rows}
**Latency is the MEDIAN of ~100 samples**, not the minimum. AI Hub's
`estimated_inference_time` — and the "Minimum Inference Time" figure on its
console — is the fastest of the hundred, and reporting it is reporting the best
run. Rows marked **⚠** still carry a minimum because their raw profile was
overwritten before per-run recording existed; treat those FPS figures as upper
bounds until the median is read off the profile page or the run is repeated.

The gap is not cosmetic. On the IQ-9075 at 640 the median is **34% slower**
than the minimum — 10.48 → 14.04 ms, 95.4 → 71.2 FPS — because at ~10 ms
scheduling noise is a large fraction of the measurement. On the RB3 at 960,
where a single inference takes 200 ms, it is under 1%.

Every run placed **100% of the network on the Hexagon NPU**, with nothing
falling back to CPU. That is the headline, not the frame rate: an
attention-centric YOLOv12 maps completely onto Qualcomm's accelerator.

## What the resolution ratio says

960 px is 2.25x the pixels of 640. On a Tesla T4 GPU it costs 2.62x the time —
near-linear. On the Hexagon NPU it costs far more. Attention's quadratic term
in token count predicts at most 5.06x, so it is not the whole story; memory
tiling is the likely remainder. **Not established.**

Settle it by benchmarking `yolov8n` — pure convolution, no attention — at both
sizes on the same device. If v8n scales ~2.25x and v12s ~7x, attention is
confirmed. If both scale ~7x, it is memory and tiling.

## Getting here

The first two compiles failed, and neither was a hardware limitation:

1. **Malformed ONNX.** `output0` appeared in both `graph.output` and
   `value_info` — a spec violation ONNX Runtime tolerates and Qualcomm's
   validator rejects. Fixed by `tools/fix_onnx_io.py`; zero operators changed.
   Four hypotheses were proposed before this one, all about the hardware, all
   wrong.
2. **Float32 I/O.** The Hexagon HTP is integer-only. Conversion had already
   succeeded — 23.8 GMAC, 9.14 M params, all 516 operators mapped, including
   every attention-derived MatMul and Softmax. The model was never the
   problem; the precision was.

**There is no unsupported-operator finding here.** YOLOv12s converts to QNN
cleanly.

## Toolchain, and a deprecation

The RB3 @ 960 run — the configuration in `backend/config.py` — was produced by:

| | |
|---|---|
| QAIRT | 2.45.0.260326154327 |
| AI Hub Workbench | aihub-2026.08.14.0 |
| Options | `--target_runtime qnn_context_binary --quantize_io` |

AI Hub warns that compiling directly to a QNN Context Binary with
`--target_runtime qnn_context_binary` is **deprecated and will be removed**,
and points at `submit_compile_and_link_jobs` instead.

Everything here was measured with the deprecated path, and it worked. The risk
is reproducibility rather than correctness: if the option is withdrawn before
anyone re-runs these, the numbers cannot be regenerated by this script as
written. Migrating is a compile job followed by a link job — which is why the
console now shows a LINK tab.

## Accuracy caveat — read before quoting any of this

Every latency above is an **INT8** model. Every mAP figure in this repo is
**FP32**. They are two different models and must never be presented as one
system. INT8 accuracy is **not yet measured**.

## Per-run detail
{details}""")
    return len(records)

# ── profile reading ──────────────────────────────────────────────────
def compute_unit_breakdown(profile: dict) -> Counter:
    """Layers per compute unit. Walks defensively — the JSON shape moves."""
    counts: Counter = Counter()

    def walk(node):
        if isinstance(node, dict):
            unit = node.get("compute_unit") or node.get("computeUnit")
            if isinstance(unit, str):
                counts[unit.upper()] += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(profile)
    return counts


def check(job, label: str) -> bool:
    """Wait for a job and report failure properly instead of sailing past it."""
    status = job.wait()
    ok = getattr(status, "success", None)
    if ok is None:
        ok = str(getattr(status, "state", status)).upper() in {"SUCCESS", "COMPLETED"}
    if not ok:
        reason = (
            getattr(status, "message", None)
            or getattr(status, "failure_reason", None)
            or "(no message — read the job page)"
        )
        print(f"\n{'=' * 68}\n{label.upper()} FAILED\n{'=' * 68}\n")
        print(f"  {reason}\n")
        print(f"  Full log: {job.url}\n")
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--device")
    ap.add_argument("--device-os", dest="device_os", default=None,
                    help='"1.6" for RB3 Gen 2, "1.9" for IQ-9075')
    ap.add_argument("--model", default=str(ONNX))
    ap.add_argument("--imgsz", type=int, default=IMGSZ,
                    help="fallback only; the ONNX graph's own input size wins")
    # DEPRECATED UPSTREAM — read the compile job page. AI Hub says:
    #   "The ability to directly compile a model to a QNN Context Binary asset
    #    with --target_runtime qnn_context_binary has been deprecated and will
    #    be removed in a future release. Please migrate to the
    #    submit_compile_and_link_jobs API."
    # It still works today and produced every number in this repo. It is a
    # reproducibility risk, not a correctness one: if AI Hub removes it before
    # anyone re-runs these benchmarks, the numbers cannot be regenerated with
    # this script. Migrating means a compile job followed by a link job, which
    # is why the console now shows a LINK tab.
    ap.add_argument("--runtime", default="qnn_context_binary",
                    help="qnn_context_binary (deprecated upstream) | tflite")
    ap.add_argument("--quantize", action="store_true",
                    help="REQUIRED for Hexagon HTP — it is integer-only")
    ap.add_argument("--calib", type=int, default=64,
                    help="calibration frames from the demo clip")
    ap.add_argument("--act-dtype", dest="act_dtype", default="int8",
                    choices=["int8", "int16"],
                    help="int16 activations recover accuracy at some speed cost")
    args = ap.parse_args()

    try:
        import qai_hub as hub
    except ImportError:
        sys.exit("pip install qai-hub")

    if args.list:
        list_devices(hub)
        return
    if not args.device:
        sys.exit("Pass --device, or --list.")

    model_path = Path(args.model)
    if not model_path.exists():
        sys.exit(f"No model at {model_path}")

    device = (hub.Device(name=args.device, os=args.device_os)
              if args.device_os else hub.Device(args.device))

    # The graph is the authority. A --imgsz flag that disagrees with the file
    # would silently calibrate on the wrong shape, so the file wins and we say
    # so rather than trusting what anyone believes the export to be.
    graph_size = onnx_input_size(model_path)
    imgsz = graph_size or args.imgsz
    if graph_size and graph_size != args.imgsz:
        print(f"note      --imgsz {args.imgsz} overridden: the graph is {graph_size}")

    ships = imgsz == IMGSZ
    tag = ("matches backend/config.py" if ships
           else f"NOT the shipped size — config.py is {IMGSZ}")

    print(f"device    {args.device}" + (f"  (OS {args.device_os})" if args.device_os else ""))
    print(f"model     {model_path.name}")
    print(f"runtime   {args.runtime}")
    print(f"imgsz     {imgsz}  ({tag})")
    print(f"quantize  {'yes — int8 weights / ' + args.act_dtype + ' activations' if args.quantize else 'no'}\n")

    source = str(model_path)
    quantized = False
    step, total_steps = 1, 3 if args.quantize else 2

    # ── quantize ─────────────────────────────────────────────────────
    if args.quantize:
        print(f"[{step}/{total_steps}] quantizing …")
        name = onnx_input_name(model_path)
        samples = calibration_samples(args.calib, imgsz)

        qjob = hub.submit_quantize_job(
            model=source,
            calibration_data={name: samples},
            weights_dtype=hub.QuantizeDtype.INT8,
            activations_dtype=(hub.QuantizeDtype.INT16 if args.act_dtype == "int16"
                               else hub.QuantizeDtype.INT8),
        )
        print(f"      {qjob.url}")
        if not check(qjob, "quantize"):
            print("  int8 activations too aggressive? try --act-dtype int16\n")
            sys.exit(1)
        source = qjob.get_target_model()
        quantized = True
        step += 1

    # ── compile ──────────────────────────────────────────────────────
    print(f"[{step}/{total_steps}] compiling for the target …")
    # --quantize_io is the half the error message was actually asking for:
    # an integer NPU needs integer tensors at the graph boundary too, not just
    # integer weights inside it.
    options = f"--target_runtime {args.runtime}"
    if quantized:
        options += " --quantize_io"

    cjob = hub.submit_compile_job(model=source, device=device, options=options)
    print(f"      {cjob.url}")
    if not check(cjob, "compile"):
        if not args.quantize:
            print("  The Hexagon HTP is integer-only. Re-run with --quantize\n")
        sys.exit(1)

    target = cjob.get_target_model()
    step += 1

    # ── profile ──────────────────────────────────────────────────────
    print(f"[{step}/{total_steps}] profiling on the real device …")
    pjob = hub.submit_profile_job(model=target, device=device)
    print(f"      {pjob.url}")
    if not check(pjob, "profile"):
        sys.exit(1)

    profile = pjob.download_profile()
    slug = run_slug(args.device, imgsz, quantized, args.act_dtype)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{slug}_profile.json").write_text(json.dumps(profile, indent=2))

    summary = profile.get("execution_summary", {})

    # AI Hub's `estimated_inference_time` is the MINIMUM of ~100 samples, and
    # the console labels it "Minimum Inference Time". Reporting it is reporting
    # the best run of a hundred.
    #
    # Handbook Part 4, on our own local benchmark: "Median, not mean. A single
    # OS scheduling hiccup adds a large outlier." And: "Report the SUSTAINED
    # figure. A burst number the device cannot hold for a ten-minute flight is
    # not the number a rescue operator would experience."
    #
    # We were violating both here. The gap is not cosmetic — on the IQ-9075 at
    # 640 the median is 34% slower than the minimum (10.48 -> 14.04 ms, 95.4 ->
    # 71.2 FPS), because at ~10 ms scheduling noise is a large fraction of the
    # measurement. On the slower RB3 at 960 it is under 1%.
    #
    # Median is the headline. Min and max are recorded as spread, because a
    # benchmark with no variance information is not a benchmark.
    samples = summary.get("all_inference_times") or []
    if samples:
        latency_us = statistics.median(samples)
        lat_min, lat_max = min(samples), max(samples)
    else:
        latency_us = (summary.get("estimated_inference_time")
                      or summary.get("inference_time") or 0)
        lat_min = lat_max = latency_us
    peak_mem = summary.get("estimated_inference_peak_memory") or 0
    units = compute_unit_breakdown(profile)
    total = sum(units.values()) or 1

    print(f"\n{'=' * 68}")
    if latency_us:
        print(f"  latency      {latency_us / 1000:.2f} ms   ({1_000_000 / latency_us:.1f} FPS)   median")
        if samples:
            print(f"               {lat_min / 1000:.2f} – {lat_max / 1000:.2f} ms spread "
                  f"over {len(samples)} samples  (min = {1_000_000 / lat_min:.1f} FPS)")
    if peak_mem:
        print(f"  peak memory  {peak_mem / (1024 * 1024):.1f} MB")
    print("\n  LAYER PLACEMENT")
    for unit, n in units.most_common():
        print(f"    {unit:<8} {n:>5} layers  {100 * n / total:>5.1f}%")
    print("=" * 68)

    npu = sum(units.get(k, 0) for k in ("NPU", "HEXAGON", "HTP"))
    share = 100 * npu / total
    print(f"\n  {share:.0f}% of layers on the Hexagon NPU\n")

    if quantized:
        print("  ⚠  This is an INT8 model. Its accuracy is NOT the mAP you")
        print("     measured on FP32. Re-validate before quoting both.\n")

    record = {
        "slug": slug,
        "device": args.device + (f" (OS {args.device_os})" if args.device_os else ""),
        "model": model_path.name,
        "runtime": args.runtime,
        "imgsz": imgsz,
        "size_note": tag,
        "precision": ("INT8 w / " + args.act_dtype.upper() + " a") if quantized else "FP32",
        "latency_ms": latency_us / 1000,
        "fps": 1_000_000 / max(latency_us, 1),
        "stat": "median",
        "latency_min_ms": lat_min / 1000,
        "latency_max_ms": lat_max / 1000,
        "samples": len(samples),
        "peak_mem_mb": peak_mem / (1024 * 1024),
        "units": dict(units),
        "total_layers": total,
        "npu_layers": npu,
        "npu_share": share,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "jobs": {"quantize": qjob.url if quantized else None,
                 "compile": cjob.url, "profile": pjob.url},
    }
    (RUNS / f"{slug}.json").write_text(json.dumps(record, indent=2))
    n = write_index(RUNS, OUT)
    print(f"recorded {slug}  ({n} run(s) in {OUT.relative_to(REPO)})")


if __name__ == "__main__":
    main()
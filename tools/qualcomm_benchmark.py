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
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ONNX = REPO / "models" / "yolov12s_960.onnx"
CLIP = REPO / "backend" / "data" / "demo_clip.mp4"
OUT = REPO / "experiments" / "QUALCOMM_BENCHMARK.md"

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
    ap.add_argument("--runtime", default="qnn_context_binary",
                    help="qnn_context_binary | tflite")
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
    raw = REPO / "experiments" / "qualcomm_profile.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps(profile, indent=2))

    summary = profile.get("execution_summary", {})
    latency_us = (summary.get("estimated_inference_time")
                  or summary.get("inference_time") or 0)
    peak_mem = summary.get("estimated_inference_peak_memory") or 0
    units = compute_unit_breakdown(profile)
    total = sum(units.values()) or 1

    print(f"\n{'=' * 68}")
    if latency_us:
        print(f"  latency      {latency_us / 1000:.2f} ms   ({1_000_000 / latency_us:.1f} FPS)")
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

    OUT.write_text(f"""# Qualcomm on-device benchmark

Measured on Qualcomm AI Hub — a hosted physical device, not an emulator.

| | |
|---|---|
| Device | `{args.device}`{f' (OS {args.device_os})' if args.device_os else ''} |
| Model | `{model_path.name}` |
| Precision | {'INT8 weights / ' + args.act_dtype.upper() + ' activations' if quantized else 'FP32'} |
| Runtime | `{args.runtime}` |
| Input size | {imgsz} ({tag}) |
| Latency | {latency_us / 1000:.2f} ms ({1_000_000 / max(latency_us, 1):.1f} FPS) |
| Peak memory | {peak_mem / (1024 * 1024):.1f} MB |
| Layers on NPU | {share:.0f}% |

## Layer placement

| Compute unit | Layers | Share |
|---|---|---|
""" + "".join(f"| {u} | {n} | {100 * n / total:.1f}% |\n" for u, n in units.most_common()) + f"""
## Getting here

The first two compiles failed, and neither was a hardware limitation:

1. **Malformed ONNX.** `output0` appeared in both `graph.output` and
   `value_info` — a spec violation ONNX Runtime tolerates and Qualcomm's
   validator rejects. Fixed by `tools/fix_onnx_io.py`; zero operators changed.
2. **Float32 I/O.** The QCS6490 Hexagon HTP is integer-only. Conversion had
   already succeeded — 23.8 GMAC, 9.14 M params, all 516 operators mapped,
   including every attention-derived MatMul and Softmax. The model was never
   the problem; the precision was.

**There is no unsupported-operator finding here.** YOLOv12s converts to QNN
cleanly.

{'⚠ **Accuracy caveat.** These numbers are for an INT8 model. The mAP figures elsewhere in this repo are FP32. Re-validate the quantized model before presenting both.' if quantized else ''}

Quantize/compile/profile jobs: {cjob.url}
Raw profile: `experiments/qualcomm_profile.json`
""")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
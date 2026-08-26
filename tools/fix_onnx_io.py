#!/usr/bin/env python3
"""
Strip graph inputs/outputs out of ONNX `value_info`.

    python tools/fix_onnx_io.py models/yolov12s_960.onnx
    python tools/fix_onnx_io.py models/*.onnx

WHY THIS EXISTS
    Qualcomm AI Hub rejects our exports with:

        Tensors {'output0'} occur in value_info but also in model IO.

    The ONNX spec is explicit that `graph.value_info` carries type information
    for tensors that are NEITHER graph inputs NOR graph outputs — it is for the
    intermediates. Ultralytics' export (via onnxslim, which `simplify=True`
    invokes) leaves `output0` in both places, which is a spec violation.

    ONNX Runtime tolerates it, which is why our local benchmarks never noticed.
    AI Hub's compiler validates strictly and refuses the model. Nothing about
    the network is wrong — the file's metadata is.

    That distinction matters for the write-up: this was never a Hexagon NPU
    limitation, an attention-operator problem, a quantization requirement or an
    activation-size ceiling. It was a malformed header, and the fix removes
    zero operators and changes zero weights.

WHAT IT DOES
    Removes any value_info entry whose name also appears in graph.input or
    graph.output, runs the official checker, and writes the file back.
"""

import shutil
import sys
from pathlib import Path


def fix(path: Path, in_place: bool = True) -> bool:
    import onnx

    model = onnx.load(str(path))
    graph = model.graph

    io_names = {t.name for t in graph.input} | {t.name for t in graph.output}
    offenders = [v.name for v in graph.value_info if v.name in io_names]

    print(f"\n{path.name}")
    print(f"  inputs       {[t.name for t in graph.input]}")
    print(f"  outputs      {[t.name for t in graph.output]}")
    print(f"  value_info   {len(graph.value_info)} entries")

    if not offenders:
        print("  already clean — nothing to do")
        return False

    print(f"  OFFENDING    {offenders}")

    keep = [v for v in graph.value_info if v.name not in io_names]
    del graph.value_info[:]
    graph.value_info.extend(keep)

    # Fail loudly rather than writing a file that breaks somewhere further
    # downstream where the cause would be much harder to find.
    onnx.checker.check_model(model)

    if in_place:
        backup = path.with_suffix(path.suffix + ".orig")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"  backup       {backup.name}")
        out = path
    else:
        out = path.with_name(path.stem + "_fixed" + path.suffix)

    onnx.save(model, str(out))
    print(f"  value_info   {len(keep)} entries after")
    print(f"  wrote        {out.name}  ✓ checker passed")
    return True


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        sys.exit(__doc__)

    missing = [p for p in paths if not p.exists()]
    if missing:
        sys.exit(f"Not found: {', '.join(str(p) for p in missing)}")

    changed = sum(fix(p) for p in paths)
    print(f"\n{changed} of {len(paths)} file(s) modified.")
    if changed:
        print("\nRe-run the benchmark — the originals are kept as .onnx.orig")


if __name__ == "__main__":
    main()

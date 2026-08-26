# Qualcomm on-device benchmark

Measured on Qualcomm AI Hub — a hosted physical device, not an emulator.

| | |
|---|---|
| Device | `Dragonwing IQ-9075 EVK` (OS 1.9) |
| Model | `yolov12s_640.onnx` |
| Precision | INT8 weights / INT8 activations |
| Runtime | `qnn_context_binary` |
| Input size | 640 (NOT the shipped size — config.py is 960) |
| Latency | 10.48 ms (95.4 FPS) |
| Peak memory | 6.5 MB |
| Layers on NPU | 100% |

## Layer placement

| Compute unit | Layers | Share |
|---|---|---|
| NPU | 489 | 100.0% |

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

⚠ **Accuracy caveat.** These numbers are for an INT8 model. The mAP figures elsewhere in this repo are FP32. Re-validate the quantized model before presenting both.

Quantize/compile/profile jobs: https://workbench.aihub.qualcomm.com/jobs/jgj7ol1xg/
Raw profile: `experiments/qualcomm_profile.json`

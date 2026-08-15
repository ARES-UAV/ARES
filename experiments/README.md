# Experiments

This directory contains reproducible experiments and evaluation
results for ARES.

## Completed Experiments

### AI Detection — YOLOv8n on C2A

A YOLOv8n COCO-pretrained baseline was evaluated on the C2A Human
Detection test set and compared with a YOLOv8n model fine-tuned on C2A.

- Test images: 2,043
- Test instances: 72,523

| Metric | YOLOv8n Baseline | YOLOv8n C2A Fine-tuned |
|---|---:|---:|
| Precision | 0.312 | **0.843** |
| Recall | 0.189 | **0.728** |
| mAP50 | 0.131 | **0.774** |
| mAP50-95 | 0.060 | **0.488** |
| Inference latency | — | **4.4 ms/image** |

The C2A fine-tuned model showed substantial improvement over the
COCO-pretrained baseline, particularly in mAP and recall.

### Current Finding

C2A-specific fine-tuning significantly improves YOLOv8n human
detection performance on the C2A test set.

The experiment provides the baseline for comparison with larger YOLO
models.

## Planned Experiments

### AI Detection
- RGB detection performance
- Small-object detection
- Precision
- Recall
- mAP
- Inference latency
- FPS

### Sensor Fusion
- RGB-only
- Thermal-only
- RGB + thermal

### Localization
- Survivor coordinate estimation
- Localization error
- Effect of altitude and camera angle

### Search Algorithms
- Random search
- Grid/lawn-mower search
- Nearest-target search
- ARES adaptive search

### Mission Performance

Algorithms will be compared using:

- Survivors detected
- Time to first survivor
- Time to locate all survivors
- Search coverage
- Flight distance
- Estimated energy consumption
- Localization accuracy

## Experiment Policy

Experiments should record:

- Configuration
- Dataset/version
- Model/version
- Parameters
- Number of trials
- Results
- Conclusions

## Status

### Completed
- YOLOv8n COCO-pretrained baseline evaluation on C2A
- YOLOv8n C2A fine-tuning
- YOLOv8n test evaluation
- Baseline vs fine-tuned comparison

### Next
- YOLOv8s baseline and C2A fine-tuning
- YOLOv8m baseline and C2A fine-tuning
- Model comparison and selection
- Further ARES detection, fusion, localization, and mission experiments

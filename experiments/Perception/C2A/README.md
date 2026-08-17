# C2A — Human Detection in Disaster Scenarios

C2A (Combination to Application) is a dataset designed for human
detection in disaster scenarios using UAV/aerial imagery.

For ARES, C2A is used as one of the primary datasets for evaluating
and fine-tuning human detection models for autonomous aerial
search-and-rescue missions.

---

## Dataset

**Official Kaggle Dataset:**

https://www.kaggle.com/datasets/rgbnihal/c2a-dataset

The C2A dataset contains:

- 10,215 images
- 360,000+ annotated human instances
- 4 disaster scenario categories
- 5 human pose categories
- Bounding-box annotations
- UAV/aerial disaster imagery

### Disaster Scenarios

The dataset includes:

- Fire / Smoke
- Flood
- Collapsed Buildings / Rubble
- Traffic Accidents

### Human Poses

The dataset contains different human poses, including:

- Bent
- Kneeling
- Lying
- Sitting
- Upright

---

## Dataset Construction

C2A is a synthetic dataset created by combining disaster-scene
backgrounds with human pose information.

The disaster backgrounds are derived from the AIDER dataset,
while human pose information is derived from LSP/MPII-MPHB.

This combination is intended to create challenging human-detection
scenarios representative of disaster-response environments.

---

## Role in ARES

C2A is used primarily for:

1. Human detection in disaster environments
2. Small / difficult human detection
3. Evaluation of different YOLO architectures
4. Model fine-tuning
5. Comparison of pretrained and disaster-specific models
6. Evaluation of generalization when combined with other datasets

The C2A experiments form the first stage of the ARES perception
pipeline.

---

## ARES Detection Experiments

The current experimental workflow is:

```text
COCO-pretrained YOLO
        ↓
Baseline evaluation on C2A
        ↓
Fine-tuning on C2A
        ↓
C2A test evaluation
        ↓
Model comparison
        ↓
Selection of candidate detector
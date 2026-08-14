# ARES
### Adaptive Rescue and Exploration System

An AI-assisted autonomous UAV system for disaster-zone
search, survivor detection, and localization.

ARES aims to improve UAV search-and-rescue efficiency by
dynamically adapting its search strategy according to
detected survivors, uncertainty, environmental risk,
and remaining mission energy.

> 🚧 **Project Status:** Research and software prototyping

---

## Overview

During disaster response, rapidly locating survivors is
critical. UAVs can search large areas quickly, but
limited battery, uncertain survivor locations, obstacles,
and changing environmental conditions make efficient
search challenging.

Conventional UAV search systems often rely on predefined
search patterns. ARES investigates an alternative approach
in which the UAV continuously updates its search strategy
using information collected during the mission.

The project combines:

- UAV autonomy
- Computer vision
- RGB and thermal perception
- Survivor detection and tracking
- Survivor localization
- Risk-aware prioritization
- Adaptive search planning
- Energy-aware mission planning
- Ground-station monitoring

---

## System Architecture


                         UAV
                          │
               ┌──────────┴──────────┐
               │                     │
          RGB Camera            Thermal Camera
               │                     │
               └──────────┬──────────┘
                          ↓
                   AI Detection
                          ↓
                     Tracking
                          ↓
                   Sensor Fusion
                          ↓
                Survivor Localization
                          ↓
                  Risk Estimation
                          ↓
               Adaptive Search Planner
                          ↓
                    UAV Navigation
                          ↓
                   Ground Station


---

## System Architecture

Instead of following a fixed search pattern, ARES aims to
continuously determine which region of the disaster area should
be searched next.

The planner may consider:

* Survivor probability
* Detection confidence
* Search uncertainty
* Survivor priority
* Distance
* Estimated energy cost
* Previously searched regions
* Remaining mission time

The proposed approach will be compared with conventional search
strategies such as grid and random search.

---

## Development Roadmap

Research & Software

* Initial problem definition
* Literature review
* Dataset preparation
* Human detection
* Object tracking
* Survivor localization
* Search simulation
* Adaptive search algorithm

UAV Integration

* Hardware selection
* UAV assembly
* Telemetry
* Camera integration
* Waypoint navigation
* Autonomous mission

Research Validation

* Controlled experiments
* Baseline comparison
* Ablation study
* Results
* Research paper

---
## Repository Structure

- [**docs/**](./docs/) — Research and technical documentation
  - [project_overview.md](./docs/project_overview.md)
  - [research_problem.md](./docs/research_problem.md)
  - [roadmap.md](./docs/roadmap.md)

- [**ai/**](./ai/) — Computer vision and AI
  - [README.md](./ai/README.md)

- [**planning/**](./planning/) — Search and planning algorithms
  - [README.md](./planning/README.md)

- [**simulation/**](./simulation/) — Disaster and UAV simulation
  - [README.md](./simulation/README.md)

- [**experiments/**](./experiments/) — Experiments and evaluation
  - [README.md](./experiments/README.md)

- [**hardware/**](./hardware/) — UAV hardware and CAD
  - [README.md](./hardware/README.md)

- **README.md** — Project overview
- **LICENSE** — Project license
- **requirements.txt** — Python dependencies
- **.gitignore** — Git configuration
 
---

## Status

ARES is currently in the research and software prototyping
phase.

The initial focus is on validating the AI, simulation,
localization, and adaptive planning components before physical
UAV integration.

---

## Team

ARES Research & Development Team

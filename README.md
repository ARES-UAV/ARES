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

```text
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

                   

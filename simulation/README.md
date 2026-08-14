# Simulation

This directory contains the simulation environment used to
develop and evaluate ARES before physical UAV deployment.

## Objectives

The simulation should allow us to test:

- Disaster environments
- Obstacles
- Survivor locations
- UAV movement
- Search algorithms
- Camera observations
- Detection uncertainty
- Battery/energy constraints
- Mission time
- Search coverage

## Planned Simulation Pipeline

Disaster Environment
↓
UAV
↓
Camera Observation
↓
Survivor Detection
↓
Localization
↓
Probability/Risk Map
↓
Adaptive Planner
↓
Next Search Location
↓
UAV Movement

## Baseline Scenarios

The simulator will support comparison between:

- Random search
- Grid/lawn-mower search
- Nearest-target search
- ARES adaptive search

## Evaluation

Simulation experiments will measure:

- Search coverage
- Survivors detected
- Time to first detection
- Time to locate all survivors
- Flight distance
- Energy consumption
- Mission success rate

## Status

🚧 Simulation environment not yet implemented.

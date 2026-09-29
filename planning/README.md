# Planning

Team plans and per-group scopes. **The search and planning *code* is not in
this directory** — it lives in [`../simulation/`](../simulation/), next to the
experiment that measures it.

| File | What it is |
|---|---|
| [`PLAN_TO_30_SEPT.md`](./PLAN_TO_30_SEPT.md) | The schedule to submission, per group, with the gates and the things that were decided not to do. |
| [`G1_AI_MODEL.md`](./G1_AI_MODEL.md) | Scope for the perception group. |
| [`G2_BACKEND_FRONTEND.md`](./G2_BACKEND_FRONTEND.md) | Scope for the backend and dashboard group. |
| [`G3_DRONE_SIM.md`](./G3_DRONE_SIM.md) | Scope for the flight-simulation group. |

## Where the planner actually is

| | |
|---|---|
| The adaptive planner and the lawnmower baseline | [`../simulation/planners.py`](../simulation/planners.py) |
| The experiment that compares them | [`../simulation/run.py`](../simulation/run.py) |
| The design, written before the code | [`../simulation/DESIGN.md`](../simulation/DESIGN.md) |
| The results, 100 seeds | [`../simulation/RESULTS.md`](../simulation/RESULTS.md) |
| Rescue prioritisation — a transparent weighted score, not a model | [`../backend/priority.py`](../backend/priority.py) |
| Safe routing — A* over a risk-weighted cost grid | [`../backend/routing.py`](../backend/routing.py) |

## Status

The adaptive planner is **implemented and benchmarked in simulation**, and has
**never flown**. Both halves of that sentence matter and both appear on the
deck. Energy-aware planning exists only as a flat battery budget with a return
reserve; risk-aware prioritisation is implemented in `backend/priority.py` and
is used by the dashboard, not yet by the planner.

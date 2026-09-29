# Documentation

Everything written down about ARES lives here. Start with whichever matches
what you came for.

## Start here

| | |
|---|---|
| [`handbook/`](./handbook/) | **The engineering handbook** — thirteen parts, from what a convolution is to why the priority score is a weighted sum rather than a model. Written so that every number in the project is something a team member can explain in their own words. Begin at [`handbook/00_START_HERE.md`](./handbook/00_START_HERE.md). |
| [`index.html`](./index.html) | The public site, served at <https://ares.paralux.in> via GitHub Pages. |
| [`../experiments/ARES_MEASURED_NUMBERS.md`](../experiments/ARES_MEASURED_NUMBERS.md) | The single source of truth for every figure quoted anywhere. If a number appears in a deck, a video or on the site and is not in that file, it is a bug. |

## Recordings

| | Video |
|---|---|
| 01 | [The case for ARES](https://youtu.be/J89oZT977GU) |
| 02 | [The adaptive planner](https://youtu.be/nnc5-N-GEU4) |
| 03 | [Detection to GPS](https://youtu.be/das3HfpK2vY) |
| 04 | [The command dashboard](https://youtu.be/VloJFoPbxy4) |

## The rest of this directory

| File | What it is |
|---|---|
| [`project_overview.md`](./project_overview.md) | High-level description: objectives, architecture, intended application. |
| [`research_problem.md`](./research_problem.md) | The research question, motivation, hypothesis and intended contribution. |
| [`roadmap.md`](./roadmap.md) | Timeline, milestones and priorities. |
| [`PRIORITY_PRIOR_AND_OFFLINE.md`](./PRIORITY_PRIOR_AND_OFFLINE.md) | How the priority prior is built and how the system behaves with the network down. |
| [`ARES_ROBIN_GUIDE_v4.md`](./ARES_ROBIN_GUIDE_v4.md) | Integration guide for whoever owns the perception pipeline. |
| `img/` | Screenshots used by the site. |

## Where the other documentation lives

Not everything is in this directory, because documentation that explains a
piece of code belongs next to it:

- [`../simulation/DESIGN.md`](../simulation/DESIGN.md) and [`../simulation/RESULTS.md`](../simulation/RESULTS.md) — the adaptive-search experiment, designed before it was run and written up afterwards including the two bugs it caught.
- [`../experiments/`](../experiments/) — one file per experiment: model selection, the controlled v8s-vs-v12s re-run, the Qualcomm benchmark, the threshold derivation, the frame-rate study.
- [`../CONVENTIONS.md`](../CONVENTIONS.md) — the conventions this repository runs on, and the mistakes that produced each one.

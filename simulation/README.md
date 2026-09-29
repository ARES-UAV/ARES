# Simulation

The adaptive-search experiment. This is where the project's central claim —
that deciding where to look next beats covering ground in a fixed order — is
tested, and it is the only headline result in ARES that is simulated rather
than measured on hardware.

**There is no aircraft.** What is measured inside the simulation is the
detector: every flight runs at `P_DETECT = 0.824`, our own recall at conf 0.18
and 960 px over 86,092 instances. The terrain, the survivors and the airframe
are synthetic.

## Run it

No weights, no GPU, about six seconds:

```bash
python simulation/run.py            # 100 seeds, all three prior qualities
python simulation/check_baseline.py # proves the grid baseline is information-blind
python simulation/world.py          # prior quality vs. noise level, as a self-test
```

`run.py` writes `results/results.md`, `results/results.json` and
`results/found_vs_time.png`. The table it prints is the table in
[`RESULTS.md`](./RESULTS.md) — if they ever disagree, the code is right and the
write-up is stale.

## What it does

Both planners fly identical worlds. Same survivor layout, same detection
coin-flips, same battery. The only thing that differs is where each one chooses
to go next, so a gap between them cannot be a gap between two random maps.

| File | What it is |
|---|---|
| [`DESIGN.md`](./DESIGN.md) | The experiment, specified before the code was written. Unchanged since, deliberately — including the parts the results went on to contradict. |
| [`RESULTS.md`](./RESULTS.md) | The write-up: 100 seeds, the two bugs the experiment caught, and the case against its own conclusion. |
| `config.py` | Every constant, each tagged `assumed`, `derived`, `chosen` or `measured`. |
| `world.py` | Survivor placement, and the prior at three noise levels. |
| `planners.py` | The lawnmower baseline and the adaptive planner. |
| `run.py` | The runner. |
| `check_baseline.py` | Re-measures the baseline with and without a belief-guided return leg, to prove the control cannot use information. |
| `multi_sortie.py` | The campaign view — what the coverage trade costs across repeated sorties. |
| `render_video.py`, `export_traces.py` | The flight renderer used for the planner recording. |
| `results/` | Generated. Not hand-edited. |

## The result

Medians over 100 seeds, good prior:

| Planner | Found / 20 | Time to half | Ground covered |
|---|---:|---:|---:|
| lawnmower grid | 11.0 | 905 s | 55 % |
| **adaptive** | **20.0** | **291 s** | 33 % |

Speed-up to half the survivors: **3.11×** with a good prior, **2.10×** with a
mediocre one, **1.27×** with none at all.

The last of those is the number worth arguing about. Given a probability map no
better than chance, adaptive finds **no more people** than the grid — it only
reaches half of them sooner, by learning in flight. `RESULTS.md` § 5 states it
that way rather than quoting the 3.11× alone.

## What is not here

- **A random-search baseline.** Two lines on the chart, not three. This is the
  obvious next control and it has not been run.
- **Nearest-target search.** Same.
- **Energy modelling beyond a flat battery budget.** The battery is 1200 s with
  a 15 % return reserve and nothing more.

These were in the original plan for this directory. They are listed here rather
than quietly dropped.

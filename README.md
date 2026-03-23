# MAS Project 13 - Robot Mission 2026

## Setup

Install dependencies in your environment:

```bash
pip install mesa solara matplotlib pandas
```

## Run the simulation UI

```bash
python3 run.py
```

In the UI, use `Model Parameters` and click `RESET` to apply changes.

## Implemented strategies

- `random_no_comm` (`strategy=0`): no communication, random exploration.
- `memory_no_comm` (`strategy=1`): no communication, local memory-driven exploration.
- `comm` (`strategy=2`): communication enabled with broadcast messages.

## Communication protocol

Messages follow a structured ACL-like format:

- `id`, `performative`, `sender`, `receivers`, `content`, `timestamp`, `ttl`
- Compatibility fields: `waste_color`, `position`, `zone`

## Collected metrics

- Waste: `Green Waste`, `Yellow Waste`, `Red Waste`, `Total Waste`
- Progress: `Disposed Red Waste`, `Cleanup Time (step)`, `Objective Score`
- Communication: `Messages Sent`, `Messages Expired`, `Messages Consumed`, `Active Messages`

## Batch experiments

Run reproducible benchmarks over multiple seeds and strategies:

```bash
python3 experiments.py --runs 20 --steps 500 --output results/strategy_benchmark.csv
```

The CSV can be used for tables/plots in the final report.

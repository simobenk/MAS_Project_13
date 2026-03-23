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
- `memory_no_comm` (`strategy=10`): no communication, local memory-driven exploration.
- `comm` (`strategy=20`): communication enabled with broadcast messages.

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

## Benchmark results (current version)

Configuration:

- Command: `python3 experiments.py --runs 20 --steps 500 --output results/strategy_benchmark.csv`
- 20 runs per strategy, seeds `1000..1019`

Main results:

| Strategy         | Mean Objective Score | Mean Remaining Waste | Mean Disposed Red Waste | Mean Messages Sent | Clean-all Rate |
|------------------|----------------------|-----------------------|--------------------------|--------------------|----------------|
| `comm`           | `-55.01`             | `2.45`                | `4.15`                   | `35.55`            | `20%`          |
| `memory_no_comm` | `-282.00`            | `4.70`                | `2.65`                   | `0.00`             | `0%`           |
| `random_no_comm` | `-571.00`            | `7.10`                | `0.00`                   | `0.00`             | `0%`           |

Interpretation:

- Communication strategy (`comm`) is best on average after adding anti-spam message control.
- `memory_no_comm` improves over random but remains significantly weaker than `comm`.
- Random baseline is the least effective and never disposes red waste in this benchmark.

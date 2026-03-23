"""
Group: 13
Date: 2026-03-23
Members: Aymane Chalh, Team MAS 13
"""
import argparse
import csv
from pathlib import Path

from model import RobotMission


def run_once(strategy, seed, steps, params):
    """Run one simulation instance and return a flat metrics row."""
    model = RobotMission(strategy=strategy, seed=seed, **params)
    for _ in range(steps):
        model.step()
        if model.cleanup_time_step is not None:
            break

    return {
        "strategy": strategy,
        "seed": seed,
        "steps_executed": model.current_step,
        "cleanup_time_step": model.cleanup_time_step if model.cleanup_time_step is not None else -1,
        "total_waste": model._count_waste(),
        "waste_in_robots": model._count_inventory_waste(),
        "remaining_waste": model.remaining_waste(),
        "disposed_red_waste": model.disposed_red_waste,
        "messages_sent": model.messages_sent_total,
        "messages_expired": model.messages_expired_total,
        "messages_consumed": model.messages_consumed_total,
        "objective_score": model.objective_score(),
    }


def main():
    """Run reproducible benchmark batches and export results to CSV."""
    parser = argparse.ArgumentParser(description="Batch experiments for RobotMission strategies.")
    parser.add_argument("--runs", type=int, default=20, help="Number of runs per strategy.")
    parser.add_argument("--steps", type=int, default=500, help="Max steps per run.")
    parser.add_argument(
        "--strategies",
        type=str,
        default="random_no_comm,memory_no_comm,comm",
        help="Comma-separated strategies.",
    )
    parser.add_argument("--output", type=str, default="results/strategy_benchmark.csv")
    args = parser.parse_args()

    params = {
        "width": 15,
        "height": 10,
        "initial_green_wastes": 20,
        "num_green_robots": 4,
        "num_yellow_robots": 3,
        "num_red_robots": 2,
        "message_ttl": 10,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    rows = []
    for strategy in strategies:
        for run_index in range(args.runs):
            seed = 1000 + run_index
            rows.append(run_once(strategy, seed, args.steps, params))

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()

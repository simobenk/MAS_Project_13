"""Analyze strategy benchmark CSV files and generate summary tables/plots."""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def compute_summary(df):
    """Return aggregated stats by strategy."""
    work = df.copy()
    work["terminated"] = work["cleanup_time_step"] > 0

    grouped = work.groupby("strategy", dropna=False)
    summary = grouped.agg(
        runs=("strategy", "size"),
        termination_rate=("terminated", "mean"),
        cleanup_time_mean=("cleanup_time_step", "mean"),
        cleanup_time_std=("cleanup_time_step", "std"),
        objective_mean=("objective_score", "mean"),
        objective_std=("objective_score", "std"),
        sent_mean=("messages_sent", "mean"),
        sent_std=("messages_sent", "std"),
        disposed_mean=("disposed_red_waste", "mean"),
        disposed_std=("disposed_red_waste", "std"),
    ).reset_index()

    if {"comm_1_sent", "comm_2_sent"}.issubset(work.columns):
        comm_stats = grouped.agg(
            comm_1_sent_mean=("comm_1_sent", "mean"),
            comm_2_sent_mean=("comm_2_sent", "mean"),
            comm_1_consumed_mean=("comm_1_consumed", "mean"),
            comm_2_consumed_mean=("comm_2_consumed", "mean"),
        ).reset_index()
        summary = summary.merge(comm_stats, on="strategy", how="left")

    summary["termination_rate"] = 100 * summary["termination_rate"]
    return summary


def plot_objective_box(df, output_dir):
    """Save objective score boxplot by strategy."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    df.boxplot(column="objective_score", by="strategy", ax=ax)
    ax.set_title("Objective Score by Strategy")
    ax.set_xlabel("Strategy")
    ax.set_ylabel("Objective Score")
    fig.suptitle("")
    fig.tight_layout()
    fig.savefig(output_dir / "objective_boxplot.png", dpi=150)
    plt.close(fig)


def plot_cleanup_box(df, output_dir):
    """Save cleanup time boxplot on successful runs."""
    cleaned = df[df["cleanup_time_step"] > 0]
    if cleaned.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cleaned.boxplot(column="cleanup_time_step", by="strategy", ax=ax)
    ax.set_title("Cleanup Time by Strategy (successful runs)")
    ax.set_xlabel("Strategy")
    ax.set_ylabel("Cleanup Time (step)")
    fig.suptitle("")
    fig.tight_layout()
    fig.savefig(output_dir / "cleanup_boxplot.png", dpi=150)
    plt.close(fig)


def plot_messages_vs_score(df, output_dir):
    """Save messages-vs-score scatter plot."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for strategy, subset in df.groupby("strategy"):
        ax.scatter(subset["messages_sent"], subset["objective_score"], label=strategy, alpha=0.8)
    ax.set_title("Communication Cost vs Objective Score")
    ax.set_xlabel("Messages Sent")
    ax.set_ylabel("Objective Score")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "messages_vs_score.png", dpi=150)
    plt.close(fig)


def plot_channel_breakdown(df, output_dir):
    """Save mean comm_1 / comm_2 usage by strategy."""
    required = {"comm_1_sent", "comm_2_sent"}
    if not required.issubset(df.columns):
        return

    means = df.groupby("strategy", dropna=False)[["comm_1_sent", "comm_2_sent"]].mean()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    means.plot(kind="bar", ax=ax)
    ax.set_title("Average Message Channels by Strategy")
    ax.set_xlabel("Strategy")
    ax.set_ylabel("Messages Sent")
    ax.legend(["comm_1", "comm_2"])
    fig.tight_layout()
    fig.savefig(output_dir / "channel_breakdown.png", dpi=150)
    plt.close(fig)


def main():
    """Load CSV, compute summary and export plots."""
    parser = argparse.ArgumentParser(description="Analyze experiment CSV outputs.")
    parser.add_argument("--input", type=str, default="results/strategy_benchmark.csv")
    parser.add_argument("--output-dir", type=str, default="results/analysis")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    summary = compute_summary(df)

    summary_path = output_dir / "summary_by_strategy.csv"
    summary.to_csv(summary_path, index=False)

    plot_objective_box(df, output_dir)
    plot_cleanup_box(df, output_dir)
    plot_messages_vs_score(df, output_dir)
    plot_channel_breakdown(df, output_dir)

    print("Summary saved to", summary_path)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

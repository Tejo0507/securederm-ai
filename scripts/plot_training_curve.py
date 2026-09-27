"""
Plot federated training loss curve.

Usage:
    python -m scripts.plot_training_curve
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt

from config.settings import LOGS_DIR


def main():
    metrics_path = LOGS_DIR / "round_metrics.json"

    if not metrics_path.exists():
        print(f"No metrics file at {metrics_path}. Run training first.")
        return

    with open(metrics_path) as f:
        metrics = json.load(f)

    if not metrics:
        print("Metrics file is empty.")
        return

    rounds = [m["round"] for m in metrics]
    losses = [m["avg_loss"] for m in metrics]

    plt.figure(figsize=(8, 5))
    plt.plot(rounds, losses, "o-", linewidth=2, markersize=8, color="#2196F3")
    plt.fill_between(rounds, losses, alpha=0.1, color="#2196F3")
    plt.xlabel("Federated Round", fontsize=12)
    plt.ylabel("Average Loss", fontsize=12)
    plt.title("SecureDerm AI Federated Training Progress", fontsize=14)
    plt.xticks(rounds)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    save_path = LOGS_DIR / "federated_training.png"
    plt.savefig(save_path, dpi=150)
    print(f"Training curve saved -> {save_path}")


if __name__ == "__main__":
    main()

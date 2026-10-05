"""
SecureDerm AI — Federated Learning Demo.

Starts the aggregator server and two hospital node clients,
runs the full federated training loop using the Kaggle wound
dataset, evaluates the final model, generates plots, and
runs a prediction demo.

Usage:
    python -m scripts.run_demo
"""

import os
import secrets
import subprocess
import sys
import time
import logging
import json
import requests

from config.settings import (
    AGGREGATOR_URL,
    FEDERATED_ROUNDS,
    CHECKPOINTS_DIR,
    LOGS_DIR,
    USE_DIFFERENTIAL_PRIVACY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("demo")


def wait_for_server(url: str, timeout: int = 30) -> bool:
    """Block until the aggregator responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{url}/status", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    return False


def save_round_metrics(url: str, admin_token: str = "") -> list[dict]:
    """Fetch metrics from aggregator and save to JSON."""
    try:
        resp = requests.get(
            f"{url}/round/metrics",
            headers={"X-Node-Token": admin_token},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        metrics = data.get("metrics", [])
        metrics_path = LOGS_DIR / "round_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        return metrics
    except Exception as exc:
        logger.error("Could not fetch metrics: %s", exc)
        return []


def save_global_model(url: str, admin_token: str = "") -> bool:
    """Download final global model and save to checkpoints."""
    import base64
    import io
    import os
    import torch
    try:
        # /model/latest requires a token; without it this always got a 403
        # and the demo never produced a model to evaluate or predict with.
        resp = requests.get(
            f"{url}/model/latest",
            headers={"X-Node-Token": admin_token},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = base64.b64decode(data["weights_b64"])
        weights = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
        save_path = CHECKPOINTS_DIR / "global_model.pt"
        tmp_path = save_path.with_suffix(".pt.tmp")
        torch.save(weights, tmp_path)
        os.replace(tmp_path, save_path)  # never leave a half-written model
        logger.info("Global model saved to %s", save_path)
        return True
    except Exception as exc:
        logger.error("Could not save global model: %s", exc)
        return False


def print_training_summary(metrics: list[dict]) -> None:
    print("\n" + "=" * 50)
    print("  SecureDerm AI — Federated Training Summary")
    print("=" * 50)
    for m in metrics:
        print(f"  Round {m['round']:>2} | Nodes: {m['num_nodes']} | Avg Loss: {m['avg_loss']:.4f}")
    print("=" * 50)


def print_final_summary() -> None:
    dp_status = "Enabled" if USE_DIFFERENTIAL_PRIVACY else "Disabled"
    print("\n" + "=" * 50)
    print("  SecureDerm AI Demo Complete")
    print("=" * 50)
    print("  Hospitals participating: 2")
    print("  Dataset: Kaggle wound classification dataset")
    print(f"  Differential Privacy: {dp_status}")
    print(f"  Federated Rounds: {FEDERATED_ROUNDS}")
    print()
    print("  Training curve saved -> logs/federated_training.png")
    print("  Evaluation metrics printed above")
    print("  Prediction demo completed")
    print()
    print("  System ready for mobile deployment")
    print("=" * 50 + "\n")


def main():
    python = sys.executable
    procs: list[subprocess.Popen] = []

    try:
        # 1) Start aggregator server
        logger.info("Starting aggregator server ...")
        # One-off operator credential so this script can read metrics and
        # the final model without a hospital node's token.
        admin_token = secrets.token_urlsafe(32)
        server_proc = subprocess.Popen(
            [python, "-m", "aggregator.server"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            env={**os.environ, "AGGREGATOR_ADMIN_TOKEN": admin_token},
        )
        procs.append(server_proc)

        if not wait_for_server(AGGREGATOR_URL):
            logger.error("Aggregator did not start in time — aborting.")
            return

        logger.info("Aggregator is up at %s", AGGREGATOR_URL)

        # 2) Spawn hospital node A (partition 0)
        logger.info("Starting hospital_A client ...")
        node_a = subprocess.Popen(
            [python, "-m", "hospital_node.client",
             "--node", "hospital_A",
             "--partition", "0",
             "--rounds", str(FEDERATED_ROUNDS)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        procs.append(node_a)

        # 3) Spawn hospital node B (partition 1)
        logger.info("Starting hospital_B client ...")
        node_b = subprocess.Popen(
            [python, "-m", "hospital_node.client",
             "--node", "hospital_B",
             "--partition", "1",
             "--rounds", str(FEDERATED_ROUNDS)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        procs.append(node_b)

        # 4) Wait for both clients to finish
        logger.info("Waiting for federated training to complete ...")
        node_a.wait()
        node_b.wait()
        logger.info("All clients finished.")

        # 5) Save metrics and model
        metrics = save_round_metrics(AGGREGATOR_URL, admin_token)
        print_training_summary(metrics)
        save_global_model(AGGREGATOR_URL, admin_token)

        # 6) Evaluate global model
        logger.info("Evaluating global model ...")
        subprocess.run(
            [python, "-m", "scripts.evaluate_global_model"],
            check=False,
        )

        # 7) Generate training curve
        logger.info("Generating training curve ...")
        subprocess.run(
            [python, "-m", "scripts.plot_training_curve"],
            check=False,
        )

        # 8) Run prediction demo
        logger.info("Running prediction demo ...")
        subprocess.run(
            [python, "-m", "scripts.predict_demo"],
            check=False,
        )

        # 9) Final summary
        print_final_summary()

    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down.")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()  # a child ignoring SIGTERM must not abort cleanup
                p.wait()
        logger.info("Demo complete.")


if __name__ == "__main__":
    main()

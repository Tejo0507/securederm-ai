"""
Hospital Node Client.

Handles the full federated learning lifecycle from the hospital side:
  1. Register with the aggregation server
  2. Download the latest global model
  3. Train locally on the hospital's private dataset
  4. Upload weight updates to the server

Usage:
    python -m hospital_node.client --node hospital_A
"""

import argparse
import base64
import hashlib
import io
import os
import sys
import time
import logging

import requests
import torch

from config.settings import (
    AGGREGATOR_URL,
    DATASETS_DIR,
    FEDERATED_ROUNDS,
    KAGGLE_DATASET_DIR,
)
from hospital_node.privacy_layer import PrivacyBudgetExceeded
from hospital_node.train import train_local

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("hospital_node")

# Read from the environment rather than a CLI flag so the token doesn't
# end up in shell history or the process list.
NODE_TOKEN = os.getenv("NODE_TOKEN", "")
REGISTRATION_KEY = os.getenv("AGGREGATOR_REGISTRATION_KEY", "")
MAX_ROUND_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5


class HospitalClient:
    """Manages communication between a hospital node and the aggregator."""

    def __init__(self, hospital_id: str, dataset_path: str = "", dataset=None):
        self.hospital_id = hospital_id
        self.dataset_path = dataset_path
        self.dataset = dataset  # pre-built Dataset/Subset (Kaggle partitions)
        self.token: str | None = None
        self.budget_exhausted = False
        self.model_version: int | None = None   # version of the model last downloaded
        self.log = logging.getLogger(f"node.{hospital_id}")
        self.tag = f"[{hospital_id}]"

    # ── Registration ─────────────────────────────────────────────────
    def register(self) -> bool:
        """Register this node with the aggregation server."""
        # Determine dataset size
        if self.dataset is not None:
            dataset_size = len(self.dataset)
        else:
            from hospital_node.dataset_loader import WoundDataset
            try:
                ds = WoundDataset(self.dataset_path, training=False)
                dataset_size = len(ds)
            except (FileNotFoundError, RuntimeError) as exc:
                self.log.error("%s Cannot load dataset: %s", self.tag, exc)
                return False

        url = f"{AGGREGATOR_URL}/node/register"
        payload = {
            "hospital_id": self.hospital_id,
            "dataset_size": dataset_size,
        }

        # A restarted node can't re-register an id the aggregator already
        # knows without presenting that id's current token (anti-hijack).
        headers = {"X-Node-Token": NODE_TOKEN} if NODE_TOKEN else {}
        if REGISTRATION_KEY:
            headers["X-Registration-Key"] = REGISTRATION_KEY

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code == 409:
                self.log.error(
                    "%s '%s' is already registered with the aggregator. Set the "
                    "NODE_TOKEN environment variable to its current token to "
                    "re-register, or restart the aggregator.",
                    self.tag, self.hospital_id,
                )
                return False
            resp.raise_for_status()
        except requests.RequestException as exc:
            self.log.error("%s Registration failed: %s", self.tag, exc)
            return False

        data = resp.json()
        self.token = data["node_token"]
        self.log.info(
            "%s Registered (model v%d, %d samples)",
            self.tag, data["model_version"], dataset_size,
        )
        return True

    # ── Download model ───────────────────────────────────────────────
    def download_model(self) -> dict | None:
        """Fetch the latest global model weights from the aggregator."""
        url = f"{AGGREGATOR_URL}/model/latest"
        headers = {"X-Node-Token": self.token or ""}

        try:
            resp = requests.get(url, headers=headers, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            self.log.error("%s Model download failed: %s", self.tag, exc)
            return None

        try:
            data = resp.json()
            raw = base64.b64decode(data["weights_b64"])
            weights = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
        except Exception as exc:
            self.log.error("%s Received an unreadable model: %s", self.tag, exc)
            return None
        self.model_version = data["model_version"]
        self.log.info("%s Downloading model v%d", self.tag, self.model_version)
        return weights

    # ── Upload update ────────────────────────────────────────────────
    def upload_update(self, weights: dict, num_samples: int, loss: float) -> bool:
        """Send locally-trained weights to the aggregator."""
        buffer = io.BytesIO()
        torch.save(weights, buffer)
        raw = buffer.getvalue()
        weights_b64 = base64.b64encode(raw).decode("utf-8")

        url = f"{AGGREGATOR_URL}/training/update"
        headers = {"X-Node-Token": self.token or ""}
        payload = {
            "hospital_id": self.hospital_id,
            "model_weights_b64": weights_b64,
            "num_samples": num_samples,
            "training_loss": loss,
            "base_version": self.model_version,
            "weights_sha256": hashlib.sha256(raw).hexdigest(),
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as exc:
            self.log.error("%s Upload failed: %s", self.tag, exc)
            return False

        data = resp.json()
        self.log.info(
            "%s Sending update (loss=%.4f, aggregated=%s, model v%d)",
            self.tag, loss, data["aggregated"], data["model_version"],
        )
        return True

    # ── Full round ───────────────────────────────────────────────────
    def run_round(self, round_num: int = 0) -> bool:
        """Execute one full federated learning round."""
        self.log.info("%s Training round %d", self.tag, round_num)

        # 1) Download latest model
        global_weights = self.download_model()
        if global_weights is None:
            # Training from a fresh ImageNet init and uploading it would
            # average an unrelated model into the global one.
            self.log.error("%s No global model — skipping round %d", self.tag, round_num)
            return False

        # 2) Train locally
        self.log.info("%s Training locally ...", self.tag)
        try:
            result = train_local(
                dataset_path=self.dataset_path or None,
                dataset=self.dataset,
                global_weights=global_weights,
                node_id=self.hospital_id,
            )
        except PrivacyBudgetExceeded as exc:
            # Retrying can't help: the lifetime budget is spent. Say so
            # clearly and let main() stop retrying (it checks this flag).
            self.log.error("%s %s", self.tag, exc)
            self.budget_exhausted = True
            return False
        except Exception:
            # Don't take the whole node down (or leak a traceback that may
            # include file paths) over one failed round.
            self.log.exception("%s Local training failed", self.tag)
            return False
        self.log.info("%s Local loss: %.4f", self.tag, result["loss"])

        # 3) Upload updated weights
        self.log.info("%s Uploading gradients", self.tag)
        success = self.upload_update(
            weights=result["weights"],
            num_samples=result["num_samples"],
            loss=result["loss"],
        )
        return success


def main():
    parser = argparse.ArgumentParser(description="SecureDerm AI — Hospital Node")
    parser.add_argument(
        "--node",
        type=str,
        required=True,
        help="Hospital identifier (e.g., hospital_A)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=FEDERATED_ROUNDS,
        help=f"Number of federated rounds (default: {FEDERATED_ROUNDS})",
    )
    parser.add_argument(
        "--partition",
        type=int,
        default=-1,
        help="Partition index for Kaggle dataset (-1 = use legacy path)",
    )
    args = parser.parse_args()

    if args.partition >= 0 and KAGGLE_DATASET_DIR.exists():
        # Load Kaggle dataset and grab this hospital's partition
        from hospital_node.dataset_loader import (
            KaggleWoundDataset, split_train_val, partition_for_hospitals,
        )
        full_ds = KaggleWoundDataset(str(KAGGLE_DATASET_DIR), training=True)
        train_ds, _ = split_train_val(full_ds)
        partitions = partition_for_hospitals(train_ds, num_hospitals=2)
        if args.partition >= len(partitions):
            logger.error(
                "--partition %d is out of range (0-%d).", args.partition, len(partitions) - 1
            )
            sys.exit(1)
        my_dataset = partitions[args.partition]
        client = HospitalClient(
            hospital_id=args.node, dataset=my_dataset,
        )
    else:
        dataset_path = str(DATASETS_DIR / args.node)
        client = HospitalClient(
            hospital_id=args.node, dataset_path=dataset_path,
        )

    # Register with aggregator
    logger.info("Registering node '%s' ...", args.node)
    if not client.register():
        logger.error("Could not register — exiting.")
        sys.exit(1)

    # Run federated rounds
    failed_rounds = 0
    for round_num in range(1, args.rounds + 1):
        logger.info("=== Round %d/%d ===", round_num, args.rounds)
        success = False
        for attempt in range(1, MAX_ROUND_ATTEMPTS + 1):
            success = client.run_round(round_num=round_num)
            if success or client.budget_exhausted:
                break
            if attempt < MAX_ROUND_ATTEMPTS:
                logger.warning(
                    "Round %d failed (attempt %d/%d) — retrying in %ds",
                    round_num, attempt, MAX_ROUND_ATTEMPTS, RETRY_DELAY_SECONDS,
                )
                time.sleep(RETRY_DELAY_SECONDS)
        if client.budget_exhausted:
            logger.error("Stopping: privacy budget exhausted.")
            sys.exit(2)
        if not success:
            failed_rounds += 1
            logger.error("Round %d failed after %d attempts.", round_num, MAX_ROUND_ATTEMPTS)
            continue
        # Brief pause between rounds to avoid hammering the server
        time.sleep(2)

    if failed_rounds:
        logger.error("%d of %d rounds failed for node '%s'.", failed_rounds, args.rounds, args.node)
        sys.exit(1)
    logger.info("All rounds complete for node '%s'.", args.node)


if __name__ == "__main__":
    main()

"""
Local training loop for a hospital node.

Trains the wound classifier on the node's private dataset and
returns updated model weights (never raw data).
"""

import copy
import logging
import math
from typing import Optional

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from config.settings import (
    BATCH_SIZE,
    DP_EPSILON,
    DP_MIN_TRAIN_SAMPLES,
    LEARNING_RATE,
    LOCAL_EPOCHS,
    USE_DIFFERENTIAL_PRIVACY,
)
from hospital_node.dataset_loader import WoundDataset
from model.architecture import WoundClassifier, build_model, get_device

logger = logging.getLogger("hospital_node")


def train_local(
    dataset_path: Optional[str] = None,
    dataset: Optional[Dataset] = None,
    global_weights: Optional[dict] = None,
    epochs: int = LOCAL_EPOCHS,
    batch_size: int = BATCH_SIZE,
    lr: float = LEARNING_RATE,
    node_id: Optional[str] = None,
) -> dict:
    """
    Run a local training round on hospital data.

    Provide either `dataset_path` (loads WoundDataset) or `dataset`
    (a pre-built Dataset/Subset for federated partitions).

    With differential privacy on and a `node_id`, the round is charged to
    that node's persistent PrivacyBudget ledger; a round that would exceed
    the lifetime budget raises PrivacyBudgetExceeded before any training.

    Returns:
        dict with keys:
            "weights"  — updated model state_dict
            "num_samples" — dataset size (needed for weighted averaging)
            "loss"     — final training loss
            "epsilon"  — privacy spent this round (None without DP)
    """
    device = get_device()

    # Build dataset and loader
    if dataset is None:
        if dataset_path is None:
            raise ValueError("Must provide either dataset_path or dataset")
        dataset = WoundDataset(dataset_path, training=True)

    if len(dataset) == 0:
        raise ValueError("Cannot train on an empty dataset.")

    # With only a handful of records, per-example clipping + noise protects
    # almost nothing (and the noise swamps the signal): each patient is a
    # large fraction of every batch. Refuse rather than ship a model that
    # claims DP but leaks individual cases.
    if USE_DIFFERENTIAL_PRIVACY and len(dataset) < DP_MIN_TRAIN_SAMPLES:
        raise ValueError(
            f"Dataset has {len(dataset)} samples; differential privacy needs at "
            f"least {DP_MIN_TRAIN_SAMPLES} (DP_MIN_TRAIN_SAMPLES) to be meaningful."
        )

    # BatchNorm (non-DP path) raises on a training batch of exactly one
    # sample, so drop a trailing singleton batch. The DP path samples its
    # own batches via Opacus, so this only matters without it.
    drop_last = (
        not USE_DIFFERENTIAL_PRIVACY
        and len(dataset) > batch_size
        and len(dataset) % batch_size == 1
    )
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,  # safer on Windows
        drop_last=drop_last,
    )

    # Initialize model
    model = build_model(pretrained=(global_weights is None), device=device)

    privacy_engine = None
    budget = None

    # Optionally apply differential privacy via Opacus
    if USE_DIFFERENTIAL_PRIVACY:
        from hospital_node.privacy_layer import (
            PrivacyBudget,
            attach_privacy_engine,
            get_privacy_spent,
            make_model_private,
        )

        if node_id:
            budget = PrivacyBudget(node_id)
            budget.check(DP_EPSILON)  # fail before spending anything

        # Must fix model for Opacus *before* loading weights,
        # because fix() changes layer types (e.g. BatchNorm → GroupNorm).
        model = make_model_private(model)
        model = model.to(device)

        if global_weights:
            # Global weights come from an already-fixed model (same architecture)
            model.load_state_dict(global_weights)

        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        model, optimizer, loader, privacy_engine = attach_privacy_engine(
            model, optimizer, loader, epochs=epochs, return_engine=True,
        )
        logger.info("Differential privacy enabled (Opacus)")
    else:
        if global_weights:
            model.load_state_dict(global_weights)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    criterion = nn.CrossEntropyLoss()

    # Training loop
    model.train()
    running_loss = 0.0

    for epoch in range(epochs):
        epoch_loss = 0.0
        batches = 0

        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            batches += 1

        avg_loss = epoch_loss / max(batches, 1)
        running_loss = avg_loss
        logger.info("  Epoch %d/%d — loss: %.4f", epoch + 1, epochs, avg_loss)

    # Extract base state_dict (unwrap if Opacus-wrapped)
    if USE_DIFFERENTIAL_PRIVACY and hasattr(model, "_module"):
        state_dict = copy.deepcopy(model._module.state_dict())
    else:
        state_dict = copy.deepcopy(model.state_dict())

    # Ship CPU tensors: the aggregator (and torch.load(map_location="cpu")
    # on the other side) shouldn't depend on this node's GPU layout.
    state_dict = {k: v.detach().cpu() for k, v in state_dict.items()}

    # Charge the budget as soon as the data has been touched, even if the run
    # is then discarded as diverged: the privacy cost was incurred regardless.
    epsilon_spent = None
    if privacy_engine is not None:
        epsilon_spent = get_privacy_spent(privacy_engine)["epsilon"]
        if budget is not None:
            budget.record(epsilon_spent)

    # A diverged run would be rejected by the aggregator anyway; failing
    # here says why and avoids uploading ~45 MB of NaNs.
    if not math.isfinite(running_loss) or any(
        v.is_floating_point() and not torch.isfinite(v).all() for v in state_dict.values()
    ):
        raise RuntimeError("Local training diverged (non-finite loss or weights).")

    return {
        "weights": state_dict,
        "epsilon": epsilon_spent,
        "num_samples": len(dataset),
        "loss": running_loss,
    }


def evaluate(model: WoundClassifier, dataset_path: str) -> dict:
    """Quick evaluation pass — returns accuracy and per-class metrics."""
    device = get_device()
    model.to(device)
    model.eval()

    dataset = WoundDataset(dataset_path, training=False)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)

    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    accuracy = correct / max(total, 1)
    return {"accuracy": accuracy, "total_samples": total, "correct": correct}

"""
Local training loop for a hospital node.

Trains the wound classifier on the node's private dataset and
returns updated model weights (never raw data).
"""

import copy
import logging
from typing import Optional, Union

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from config.settings import (
    BATCH_SIZE,
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
) -> dict:
    """
    Run a local training round on hospital data.

    Provide either `dataset_path` (loads WoundDataset) or `dataset`
    (a pre-built Dataset/Subset for federated partitions).

    Returns:
        dict with keys:
            "weights"  — updated model state_dict
            "num_samples" — dataset size (needed for weighted averaging)
            "loss"     — final training loss
    """
    device = get_device()

    # Build dataset and loader
    if dataset is None:
        if dataset_path is None:
            raise ValueError("Must provide either dataset_path or dataset")
        dataset = WoundDataset(dataset_path, training=True)

    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,  # safer on Windows
        drop_last=False,
    )

    # Initialize model
    model = build_model(pretrained=(global_weights is None), device=device)

    # Optionally apply differential privacy via Opacus
    if USE_DIFFERENTIAL_PRIVACY:
        from hospital_node.privacy_layer import make_model_private, attach_privacy_engine

        # Must fix model for Opacus *before* loading weights,
        # because fix() changes layer types (e.g. BatchNorm → GroupNorm).
        model = make_model_private(model)
        model = model.to(device)

        if global_weights:
            # Global weights come from an already-fixed model (same architecture)
            model.load_state_dict(global_weights, strict=False)

        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        model, optimizer, loader = attach_privacy_engine(
            model, optimizer, loader, epochs=epochs,
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

    return {
        "weights": state_dict,
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

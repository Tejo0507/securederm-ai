"""
Differential privacy layer using Opacus.

Wraps a training pipeline with gradient clipping and Gaussian
noise injection so that individual patient data cannot be
reverse-engineered from transmitted gradients.
"""

import json
import logging
import os
import re
import types
from pathlib import Path

from opacus import PrivacyEngine
from opacus.validators import ModuleValidator
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.models.resnet import BasicBlock, Bottleneck

from config.settings import (
    DP_EPSILON,
    DP_DELTA,
    DP_MAX_GRAD_NORM,
    DP_TOTAL_EPSILON_BUDGET,
    LOCAL_EPOCHS,
    LEARNING_RATE,
    LOGS_DIR,
)

logger = logging.getLogger("hospital_node.privacy")


def make_model_private(model: nn.Module) -> nn.Module:
    """
    Validate and fix the model for Opacus compatibility.

    Opacus requires certain layer types (e.g., BatchNorm must
    become GroupNorm) and no inplace operations. Safe to call more
    than once on the same model.
    """
    if not ModuleValidator.is_valid(model):
        model = ModuleValidator.fix(model)

    # Replace inplace ReLU — Opacus cannot handle inplace ops
    _disable_inplace_relu(model)
    # Patch ResNet residual connections to avoid inplace +=
    _patch_resnet_residuals(model)
    return model


def _disable_inplace_relu(module: nn.Module) -> None:
    """Set inplace=False on every ReLU in the module tree."""
    for child in module.modules():
        if isinstance(child, nn.ReLU) and child.inplace:
            child.inplace = False


def _basic_forward(self, x):
    identity = x
    out = self.conv1(x)
    out = self.bn1(out)
    out = self.relu(out)
    out = self.conv2(out)
    out = self.bn2(out)
    if self.downsample is not None:
        identity = self.downsample(x)
    out = out + identity  # non-inplace
    out = self.relu(out)
    return out


def _bottleneck_forward(self, x):
    identity = x
    out = self.conv1(x)
    out = self.bn1(out)
    out = self.relu(out)
    out = self.conv2(out)
    out = self.bn2(out)
    out = self.relu(out)
    out = self.conv3(out)
    out = self.bn3(out)
    if self.downsample is not None:
        identity = self.downsample(x)
    out = out + identity  # non-inplace
    out = self.relu(out)
    return out


def _patch_resnet_residuals(model: nn.Module) -> None:
    """Monkey-patch ResNet BasicBlock/Bottleneck to avoid inplace += in skip connections."""
    for m in model.modules():
        if isinstance(m, BasicBlock):
            m.forward = types.MethodType(_basic_forward, m)
        elif isinstance(m, Bottleneck):
            m.forward = types.MethodType(_bottleneck_forward, m)


def attach_privacy_engine(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    data_loader: DataLoader,
    epsilon: float = DP_EPSILON,
    delta: float = DP_DELTA,
    max_grad_norm: float = DP_MAX_GRAD_NORM,
    epochs: int = LOCAL_EPOCHS,
    return_engine: bool = False,
):
    """
    Attach Opacus PrivacyEngine to the training components.

    After this call, every optimizer.step() will automatically:
      1. Clip per-sample gradients to max_grad_norm
      2. Add calibrated Gaussian noise

    Returns (wrapped_model, wrapped_optimizer, wrapped_loader), plus the
    PrivacyEngine as a fourth item when `return_engine` is true — the engine
    is the only way to ask how much privacy budget was actually spent.
    """
    privacy_engine = PrivacyEngine()

    model, optimizer, data_loader = privacy_engine.make_private_with_epsilon(
        module=model,
        optimizer=optimizer,
        data_loader=data_loader,
        target_epsilon=epsilon,
        target_delta=delta,
        max_grad_norm=max_grad_norm,
        epochs=epochs,
    )

    if return_engine:
        return model, optimizer, data_loader, privacy_engine
    return model, optimizer, data_loader


def get_privacy_spent(privacy_engine: PrivacyEngine, delta: float = DP_DELTA) -> dict:
    """Query the current privacy budget consumption."""
    epsilon = privacy_engine.get_epsilon(delta=delta)
    return {"epsilon": epsilon, "delta": delta}


# ── Cumulative privacy budget ────────────────────────────────────────────
class PrivacyBudgetExceeded(RuntimeError):
    """Raised when another training round would exceed the node's total budget."""


class PrivacyBudget:
    """Per-node ledger of epsilon spent across federated rounds.

    Each local round gets a fresh Opacus accountant, so by itself nothing
    notices that the same patients' data is touched again every round and
    the real cumulative leakage keeps growing. This persists the spend and
    refuses to start a round that would push the total past
    DP_TOTAL_EPSILON_BUDGET. Epsilons are summed (basic sequential
    composition), a conservative upper bound.

    A budget of 0 (or less) disables enforcement; spending is still recorded.
    """

    def __init__(
        self,
        node_id: str,
        total_budget: float | None = None,
        directory: Path | None = None,
    ):
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", node_id)[:64] or "node"
        self.path = Path(directory or LOGS_DIR) / f"privacy_ledger_{safe_id}.json"
        self.total_budget = (
            DP_TOTAL_EPSILON_BUDGET if total_budget is None else total_budget
        )
        self.spent = 0.0
        self.rounds = 0
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
            self.spent = max(float(data.get("epsilon_spent", 0.0)), 0.0)
            self.rounds = int(data.get("rounds", 0))
        except FileNotFoundError:
            pass
        except (ValueError, OSError):
            # A corrupt ledger must not silently reset to "nothing spent".
            raise RuntimeError(
                f"Privacy ledger {self.path} is unreadable; fix or remove it "
                "deliberately rather than losing the recorded budget."
            )

    @property
    def remaining(self) -> float:
        if self.total_budget <= 0:
            return float("inf")
        return max(self.total_budget - self.spent, 0.0)

    def check(self, next_round_epsilon: float) -> None:
        """Raise PrivacyBudgetExceeded if the next round would overspend."""
        if self.total_budget > 0 and self.spent + next_round_epsilon > self.total_budget:
            raise PrivacyBudgetExceeded(
                f"Privacy budget exhausted: {self.spent:.2f} of "
                f"{self.total_budget:.2f} epsilon spent; the next round needs "
                f"{next_round_epsilon:.2f}."
            )

    def record(self, epsilon: float) -> None:
        self.spent += float(epsilon)
        self.rounds += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({
            "epsilon_spent": self.spent,
            "rounds": self.rounds,
            "total_budget": self.total_budget,
            "delta": DP_DELTA,
        }))
        os.replace(tmp, self.path)  # a crash mid-write must not corrupt the ledger
        logger.info(
            "Privacy budget: %.2f spent over %d rounds (remaining %s)",
            self.spent, self.rounds,
            "unlimited" if self.total_budget <= 0 else f"{self.remaining:.2f}",
        )


def train_with_privacy(
    model: nn.Module,
    data_loader: DataLoader,
    epochs: int = LOCAL_EPOCHS,
    lr: float = LEARNING_RATE,
) -> tuple[nn.Module, float, float]:
    """
    Full private training loop.

    Combines model validation, privacy engine attachment,
    and the training loop into one call.

    Returns:
        (trained_model, final_loss, epsilon_spent)
    """
    device = next(model.parameters()).device

    # Make model Opacus-compatible
    model = make_model_private(model)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Attach differential privacy
    model, optimizer, data_loader, engine = attach_privacy_engine(
        model, optimizer, data_loader, epochs=epochs, return_engine=True
    )

    model.train()
    final_loss = 0.0

    for epoch in range(epochs):
        epoch_loss = 0.0
        batches = 0

        for images, labels in data_loader:
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
        final_loss = avg_loss
        logger.info("[DP] Epoch %d/%d — loss: %.4f", epoch + 1, epochs, avg_loss)

    return model, final_loss, get_privacy_spent(engine)["epsilon"]

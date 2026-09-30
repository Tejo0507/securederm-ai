"""
Differential privacy layer using Opacus.

Wraps a training pipeline with gradient clipping and Gaussian
noise injection so that individual patient data cannot be
reverse-engineered from transmitted gradients.
"""

from opacus import PrivacyEngine
from opacus.validators import ModuleValidator
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from config.settings import (
    DP_EPSILON,
    DP_DELTA,
    DP_MAX_GRAD_NORM,
    LOCAL_EPOCHS,
    LEARNING_RATE,
)


def make_model_private(model: nn.Module) -> nn.Module:
    """
    Validate and fix the model for Opacus compatibility.

    Opacus requires certain layer types (e.g., BatchNorm must
    become GroupNorm) and no inplace operations.
    """
    if not ModuleValidator.is_valid(model):
        model = ModuleValidator.fix(model)

    # Replace inplace ReLU — Opacus cannot handle inplace ops
    _disable_inplace_relu(model)
    # Patch ResNet residual connections to avoid inplace +=
    _patch_resnet_residuals(model)
    return model


def _disable_inplace_relu(module: nn.Module) -> None:
    """Recursively set inplace=False on all ReLU layers."""
    for child_name, child in module.named_modules():
        if isinstance(child, nn.ReLU) and child.inplace:
            child.inplace = False


def _patch_resnet_residuals(model: nn.Module) -> None:
    """Monkey-patch ResNet BasicBlock/Bottleneck to avoid inplace += in skip connections."""
    from torchvision.models.resnet import BasicBlock, Bottleneck

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

    for m in model.modules():
        if isinstance(m, BasicBlock):
            import types
            m.forward = types.MethodType(_basic_forward, m)
        elif isinstance(m, Bottleneck):
            import types
            m.forward = types.MethodType(_bottleneck_forward, m)


def attach_privacy_engine(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    data_loader: DataLoader,
    epsilon: float = DP_EPSILON,
    delta: float = DP_DELTA,
    max_grad_norm: float = DP_MAX_GRAD_NORM,
    epochs: int = LOCAL_EPOCHS,
) -> tuple[nn.Module, torch.optim.Optimizer, DataLoader]:
    """
    Attach Opacus PrivacyEngine to the training components.

    After this call, every optimizer.step() will automatically:
      1. Clip per-sample gradients to max_grad_norm
      2. Add calibrated Gaussian noise

    Returns the (wrapped_model, wrapped_optimizer, wrapped_loader).
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

    return model, optimizer, data_loader


def get_privacy_spent(privacy_engine: PrivacyEngine) -> dict:
    """Query the current privacy budget consumption."""
    epsilon = privacy_engine.get_epsilon(delta=DP_DELTA)
    return {"epsilon": epsilon, "delta": DP_DELTA}


def train_with_privacy(
    model: nn.Module,
    data_loader: DataLoader,
    epochs: int = LOCAL_EPOCHS,
    lr: float = LEARNING_RATE,
) -> tuple[nn.Module, float]:
    """
    Full private training loop.

    Combines model validation, privacy engine attachment,
    and the training loop into one call.

    Returns:
        (trained_model, final_loss)
    """
    device = next(model.parameters()).device

    # Make model Opacus-compatible
    model = make_model_private(model)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Attach differential privacy
    model, optimizer, data_loader = attach_privacy_engine(
        model, optimizer, data_loader, epochs=epochs
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
        print(f"  [DP] Epoch {epoch + 1}/{epochs} — loss: {avg_loss:.4f}")

    return model, final_loss

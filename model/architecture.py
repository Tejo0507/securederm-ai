"""
Wound classification model — ResNet18 backbone.

Takes a 224x224 RGB wound image and outputs a probability
distribution over 4 infection severity classes:
  0 = Normal Healing
  1 = Mild Infection
  2 = Moderate Infection
  3 = Severe Infection
"""

import torch
import torch.nn as nn
from torchvision import models

from config.settings import NUM_CLASSES


class WoundClassifier(nn.Module):
    """ResNet18-based classifier fine-tuned for wound severity."""

    def __init__(self, num_classes: int = NUM_CLASSES, pretrained: bool = True):
        super().__init__()

        # Load a standard ResNet18 and reuse its feature extractor.
        # ImageNet pre-training gives us a solid starting point even
        # though wound images differ from natural photos.
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        self.backbone = models.resnet18(weights=weights)

        # Replace the final fully-connected layer to match our class count.
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Linear(in_features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Batch of images, shape (B, 3, 224, 224).

        Returns:
            Raw logits, shape (B, num_classes). Apply softmax externally
            if you need probabilities.
        """
        return self.backbone(x)


def build_model(pretrained: bool = True, device: str = "cpu") -> WoundClassifier:
    """Factory helper — creates and moves the model to the target device."""
    model = WoundClassifier(pretrained=pretrained)
    return model.to(device)


def get_device() -> str:
    """Pick the best available device."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"

"""Tests for the WoundClassifier model."""

import torch

from config.settings import NUM_CLASSES
from model.architecture import WoundClassifier, build_model


class TestWoundClassifier:
    def test_output_shape(self):
        model = WoundClassifier(num_classes=4, pretrained=False)
        x = torch.randn(2, 3, 224, 224)
        out = model(x)
        assert out.shape == (2, 4)

    def test_build_model_cpu(self):
        model = build_model(pretrained=False, device="cpu")
        assert isinstance(model, WoundClassifier)

    def test_forward_pass_no_error(self):
        model = build_model(pretrained=False, device="cpu")
        x = torch.randn(1, 3, 224, 224)
        out = model(x)
        assert out.shape == (1, NUM_CLASSES)
        # Logits should be finite
        assert torch.isfinite(out).all()

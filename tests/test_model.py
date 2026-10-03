"""Tests for the WoundClassifier model."""

import torch

from config.settings import NUM_CLASSES
from model.architecture import WoundClassifier, build_model


class TestBuildModelForStateDict:
    def test_loads_stock_batchnorm_checkpoint_strictly(self):
        from model.architecture import build_model_for_state_dict

        sd = build_model(pretrained=False).state_dict()
        model = build_model_for_state_dict(sd)
        assert any(k.endswith("running_mean") for k in model.state_dict())
        assert not model.training

    def test_loads_dp_groupnorm_checkpoint_strictly(self):
        from hospital_node.privacy_layer import make_model_private
        from model.architecture import build_model_for_state_dict

        sd = make_model_private(build_model(pretrained=False)).state_dict()
        model = build_model_for_state_dict(sd)
        assert not any(k.endswith("running_mean") for k in model.state_dict())

    def test_mismatched_checkpoint_raises(self):
        import pytest
        from model.architecture import build_model_for_state_dict

        sd = dict(build_model(pretrained=False).state_dict())
        sd.pop("backbone.fc.bias")
        with pytest.raises(RuntimeError):
            build_model_for_state_dict(sd)


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

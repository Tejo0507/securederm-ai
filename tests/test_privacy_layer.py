"""Tests for the differential-privacy layer and cumulative privacy budget."""

import pytest
import torch
from torch.utils.data import Dataset

from hospital_node import privacy_layer
from hospital_node import train as train_module
from hospital_node.privacy_layer import (
    PrivacyBudget,
    PrivacyBudgetExceeded,
    make_model_private,
)
from model.architecture import build_model


pytestmark = pytest.mark.privacy


class _Tiny(Dataset):
    def __len__(self):
        return 8

    def __getitem__(self, idx):
        return torch.randn(3, 32, 32), idx % 3


class TestMakeModelPrivate:
    def test_removes_batchnorm_and_is_idempotent(self):
        model = make_model_private(build_model(pretrained=False))
        keys = set(model.state_dict().keys())
        assert not any(k.endswith("running_mean") for k in keys)

        again = make_model_private(model)
        assert set(again.state_dict().keys()) == keys

    def test_no_inplace_relu_remains(self):
        model = make_model_private(build_model(pretrained=False))
        assert not any(
            isinstance(m, torch.nn.ReLU) and m.inplace for m in model.modules()
        )

    def test_forward_works_after_patching(self):
        model = make_model_private(build_model(pretrained=False)).eval()
        out = model(torch.randn(1, 3, 64, 64))
        assert torch.isfinite(out).all()


class TestPrivacyBudget:
    def test_spend_persists_across_instances(self, tmp_path):
        PrivacyBudget("node_a", total_budget=10, directory=tmp_path).record(3.0)
        again = PrivacyBudget("node_a", total_budget=10, directory=tmp_path)
        assert again.spent == pytest.approx(3.0)
        assert again.rounds == 1
        assert again.remaining == pytest.approx(7.0)

    def test_refuses_round_that_would_overspend(self, tmp_path):
        budget = PrivacyBudget("node_a", total_budget=5, directory=tmp_path)
        budget.record(3.0)
        with pytest.raises(PrivacyBudgetExceeded):
            budget.check(3.0)
        budget.check(2.0)  # exactly fits

    def test_zero_budget_disables_enforcement(self, tmp_path):
        budget = PrivacyBudget("node_a", total_budget=0, directory=tmp_path)
        budget.record(1000.0)
        budget.check(1000.0)
        assert budget.remaining == float("inf")

    def test_node_id_cannot_escape_the_directory(self, tmp_path):
        budget = PrivacyBudget("../../evil", total_budget=1, directory=tmp_path)
        assert budget.path.parent == tmp_path

    def test_corrupt_ledger_is_an_error_not_a_reset(self, tmp_path):
        (tmp_path / "privacy_ledger_node_a.json").write_text("{not json")
        with pytest.raises(RuntimeError):
            PrivacyBudget("node_a", total_budget=5, directory=tmp_path)


class TestSecureMode:
    def test_missing_csprng_gives_a_clear_error(self, monkeypatch):
        monkeypatch.setattr(privacy_layer, "DP_SECURE_MODE", True)
        try:
            import torchcsprng  # noqa: F401
        except ImportError:
            model = make_model_private(build_model(pretrained=False))
            opt = torch.optim.SGD(model.parameters(), lr=0.1)
            loader = torch.utils.data.DataLoader(_Tiny(), batch_size=4)
            with pytest.raises(RuntimeError, match="torchcsprng"):
                privacy_layer.attach_privacy_engine(model, opt, loader)
        else:
            pytest.skip("torchcsprng installed")


class TestLogHygiene:
    def test_unreadable_image_log_omits_the_filename(self, tmp_path, caplog):
        from PIL import Image

        from hospital_node.dataset_loader import KaggleWoundDataset

        folder = tmp_path / "Abrasions"
        folder.mkdir()
        Image.new("RGB", (8, 8)).save(folder / "good.png")
        (folder / "JANE_DOE_MRN4471.png").write_bytes(b"corrupt")

        ds = KaggleWoundDataset(str(tmp_path), training=False)
        with caplog.at_level("WARNING", logger="hospital_node.dataset"):
            for i in range(len(ds)):
                ds[i]
        assert "Skipping unreadable image" in caplog.text
        assert "JANE" not in caplog.text and "MRN4471" not in caplog.text

    def test_delta_not_below_one_over_n_warns(self, monkeypatch, caplog):
        monkeypatch.setattr(train_module, "DP_DELTA", 0.5)
        monkeypatch.setattr(train_module, "USE_DIFFERENTIAL_PRIVACY", True)
        with caplog.at_level("WARNING", logger="hospital_node"):
            train_module.train_local(dataset=_Tiny(), batch_size=4, epochs=1)
        assert "DP_DELTA" in caplog.text


class TestMinimumDatasetSize:
    def test_dp_refuses_tiny_datasets(self, monkeypatch):
        monkeypatch.setattr(train_module, "USE_DIFFERENTIAL_PRIVACY", True)

        class Three(_Tiny):
            def __len__(self):
                return 3

        with pytest.raises(ValueError, match="DP_MIN_TRAIN_SAMPLES"):
            train_module.train_local(dataset=Three(), batch_size=2, epochs=1)


class TestTrainLocalBudget:
    def test_round_is_charged_and_exhaustion_blocks_training(self, tmp_path, monkeypatch):
        monkeypatch.setattr(privacy_layer, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(privacy_layer, "DP_TOTAL_EPSILON_BUDGET", 5.0)
        monkeypatch.setattr(train_module, "USE_DIFFERENTIAL_PRIVACY", True)

        result = train_module.train_local(
            dataset=_Tiny(), batch_size=4, epochs=1, node_id="budget_node"
        )
        assert result["epsilon"] is not None and result["epsilon"] > 0
        assert (tmp_path / "privacy_ledger_budget_node.json").exists()

        # 5.0 budget, ~3.0 per round: the second round must be refused.
        with pytest.raises(PrivacyBudgetExceeded):
            train_module.train_local(
                dataset=_Tiny(), batch_size=4, epochs=1, node_id="budget_node"
            )

"""Tests for the hospital node: dataset helpers, local training, and client rounds."""

import pytest
import torch
from torch.utils.data import Dataset

from hospital_node import client as client_module
from hospital_node import train as train_module
from hospital_node.dataset_loader import partition_for_hospitals


pytestmark = pytest.mark.federated


class _TinyDataset(Dataset):
    def __init__(self, n):
        self.n = n

    def __len__(self):
        return self.n

    def __getitem__(self, idx):
        return torch.randn(3, 32, 32), idx % 2


class TestPartitioning:
    def test_more_hospitals_than_samples_raises(self):
        with pytest.raises(ValueError):
            partition_for_hospitals(_TinyDataset(1), num_hospitals=2)

    def test_partitions_cover_every_sample_once(self):
        parts = partition_for_hospitals(_TinyDataset(11), num_hospitals=3)
        assert sum(len(p) for p in parts) == 11


class TestTrainLocal:
    def test_empty_dataset_raises(self):
        with pytest.raises(ValueError):
            train_module.train_local(dataset=_TinyDataset(0))

    def test_trailing_singleton_batch_does_not_crash_batchnorm(self, monkeypatch):
        monkeypatch.setattr(train_module, "USE_DIFFERENTIAL_PRIVACY", False)
        # 5 samples with batch_size 4 -> a final batch of one sample, which
        # BatchNorm in train mode rejects.
        result = train_module.train_local(
            dataset=_TinyDataset(5), batch_size=4, epochs=1
        )
        assert result["num_samples"] == 5
        assert all(v.device.type == "cpu" for v in result["weights"].values())
        assert all(
            torch.isfinite(v).all() for v in result["weights"].values() if v.is_floating_point()
        )


class TestClientRounds:
    def _client(self):
        c = client_module.HospitalClient("node_x", dataset=_TinyDataset(4))
        c.token = "t"
        return c

    def test_round_is_skipped_when_global_model_unavailable(self, monkeypatch):
        c = self._client()
        monkeypatch.setattr(c, "download_model", lambda: None)

        def _must_not_train(**kwargs):
            raise AssertionError("trained without a global model")

        monkeypatch.setattr(client_module, "train_local", _must_not_train)
        assert c.run_round(1) is False

    def test_training_failure_returns_false_instead_of_crashing(self, monkeypatch):
        c = self._client()
        monkeypatch.setattr(c, "download_model", lambda: {"w": torch.zeros(1)})

        def _boom(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(client_module, "train_local", _boom)
        assert c.run_round(1) is False

    def test_registration_conflict_is_reported_not_raised(self, monkeypatch):
        class _Resp:
            status_code = 409

        monkeypatch.setattr(client_module.requests, "post", lambda *a, **k: _Resp())
        assert self._client().register() is False

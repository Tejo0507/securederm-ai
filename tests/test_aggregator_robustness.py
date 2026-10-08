"""Tests for aggregator update validation, clipping, integrity and model info."""

import hashlib
from collections import OrderedDict

import pytest
import torch
from fastapi.testclient import TestClient

import aggregator.server as server_module
from aggregator.robust import clip_update, update_norm
from aggregator.server import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register(client, name, size=50):
    return client.post("/node/register", json={
        "hospital_id": name, "dataset_size": size,
    }).json()["node_token"]


def _body(name, weights=None, **extra):
    weights = server_module.global_weights if weights is None else weights
    b64 = server_module._serialize_weights(weights)
    body = {
        "hospital_id": name, "model_weights_b64": b64,
        "num_samples": 10, "training_loss": 0.5,
    }
    body.update(extra)
    return body


class TestClipping:
    def _pair(self):
        ref = OrderedDict(w=torch.zeros(4), n=torch.tensor(3))
        new = OrderedDict(w=torch.tensor([3.0, 4.0, 0.0, 0.0]), n=torch.tensor(9))
        return new, ref

    def test_norm_ignores_integer_buffers(self):
        new, ref = self._pair()
        assert update_norm(new, ref) == pytest.approx(5.0)

    def test_far_update_is_scaled_to_the_limit(self):
        new, ref = self._pair()
        clipped, norm, was_clipped = clip_update(new, ref, 1.0)
        assert was_clipped and norm == pytest.approx(5.0)
        assert update_norm(clipped, ref) == pytest.approx(1.0, abs=1e-5)
        assert clipped["n"].item() == 9  # integer buffer untouched

    def test_near_update_and_disabled_limit_pass_through(self):
        new, ref = self._pair()
        assert clip_update(new, ref, 10.0)[2] is False
        assert clip_update(new, ref, 0)[2] is False


class TestUpdateValidation:
    def test_stale_base_version_is_rejected(self, client):
        token = _register(client, "stale_node")
        resp = client.post(
            "/training/update",
            json=_body("stale_node", base_version=server_module.model_version - 1),
            headers={"X-Node-Token": token},
        )
        assert resp.status_code == 409

    def test_corrupt_payload_fails_integrity_check(self, client):
        token = _register(client, "corrupt_node")
        resp = client.post(
            "/training/update",
            json=_body("corrupt_node", weights_sha256="0" * 64),
            headers={"X-Node-Token": token},
        )
        assert resp.status_code == 400
        assert "integrity" in resp.json()["detail"]

    def test_matching_digest_and_version_are_accepted(self, client):
        token = _register(client, "good_node")
        server_module.pending_updates.clear()
        body = _body("good_node")
        digest = hashlib.sha256(
            __import__("base64").b64decode(body["model_weights_b64"])
        ).hexdigest()
        body.update(weights_sha256=digest, base_version=server_module.model_version)
        resp = client.post("/training/update", json=body, headers={"X-Node-Token": token})
        assert resp.status_code == 200
        server_module.pending_updates.clear()

    def test_claimed_samples_are_capped_at_registered_size(self, client):
        token = _register(client, "liar_node", size=7)
        server_module.pending_updates.clear()
        body = _body("liar_node", num_samples=1_000_000)
        resp = client.post("/training/update", json=body, headers={"X-Node-Token": token})
        assert resp.status_code == 200
        pending = [u for u in server_module.pending_updates if u["hospital_id"] == "liar_node"]
        assert pending and pending[0]["num_samples"] == 7
        server_module.pending_updates.clear()

    def test_far_update_is_clipped_when_enabled(self, client, monkeypatch):
        monkeypatch.setattr(server_module, "AGGREGATOR_MAX_UPDATE_NORM", 0.5)
        token = _register(client, "far_node")
        server_module.pending_updates.clear()
        shifted = OrderedDict(
            (k, v + 1.0 if v.is_floating_point() else v)
            for k, v in server_module.global_weights.items()
        )
        resp = client.post(
            "/training/update", json=_body("far_node", shifted),
            headers={"X-Node-Token": token},
        )
        assert resp.status_code == 200
        stored = next(u for u in server_module.pending_updates if u["hospital_id"] == "far_node")
        assert update_norm(stored["weights"], server_module.global_weights) <= 0.5 + 1e-3
        server_module.pending_updates.clear()


class TestModelInfoAndIntegrity:
    def test_model_info_requires_token_and_hides_weights(self, client):
        assert client.get("/model/info").status_code == 403
        token = _register(client, "info_node")
        data = client.get("/model/info", headers={"X-Node-Token": token}).json()
        assert data["num_classes"] == 10
        assert "weights_b64" not in data and "class_labels" in data

    def test_tampered_checkpoint_is_not_restored(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "AGGREGATOR_PERSIST", True)
        monkeypatch.setattr(server_module, "CHECKPOINTS_DIR", tmp_path)
        monkeypatch.setattr(server_module, "_CHECKPOINT_PATH", tmp_path / "g.pt")
        monkeypatch.setattr(server_module, "_META_PATH", tmp_path / "g.json")
        server_module._persist_state()
        build = lambda pretrained: server_module.global_weights  # noqa: E731
        assert server_module._load_persisted_state(build) is not None

        with open(tmp_path / "g.pt", "ab") as fh:
            fh.write(b"tamper")
        assert server_module._load_persisted_state(build) is None

    def test_meta_file_is_a_model_card(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setattr(server_module, "AGGREGATOR_PERSIST", True)
        monkeypatch.setattr(server_module, "CHECKPOINTS_DIR", tmp_path)
        monkeypatch.setattr(server_module, "_CHECKPOINT_PATH", tmp_path / "g.pt")
        monkeypatch.setattr(server_module, "_META_PATH", tmp_path / "g.json")
        server_module._persist_state()
        meta = json.loads((tmp_path / "g.json").read_text())
        assert {"model_version", "sha256", "class_labels", "differential_privacy"} <= set(meta)

"""Tests for the aggregation server API."""

import pytest
from fastapi.testclient import TestClient

from aggregator.server import app


pytestmark = pytest.mark.federated


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestServerEndpoints:
    def test_status(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert "model_version" in data

    def test_register_node(self, client):
        resp = client.post("/node/register", json={
            "hospital_id": "test_hospital",
            "dataset_size": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "node_token" in data
        assert data["model_version"] >= 1

    def test_get_latest_model_requires_token(self, client):
        resp = client.get("/model/latest")
        assert resp.status_code == 403

    def test_get_latest_model_with_valid_token(self, client):
        reg = client.post("/node/register", json={
            "hospital_id": "model_dl_hospital",
            "dataset_size": 100,
        })
        token = reg.json()["node_token"]
        resp = client.get("/model/latest", headers={"X-Node-Token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert "weights_b64" in data
        assert data["model_version"] >= 1

    def test_submit_update_requires_token(self, client):
        resp = client.post("/training/update", json={
            "hospital_id": "unknown",
            "model_weights_b64": "",
            "num_samples": 10,
            "training_loss": 0.5,
        }, headers={"X-Node-Token": "bad_token"})
        assert resp.status_code == 403

    def test_submit_update_rejects_non_positive_samples(self, client):
        reg = client.post("/node/register", json={
            "hospital_id": "bad_samples_hospital",
            "dataset_size": 100,
        })
        token = reg.json()["node_token"]
        resp = client.post("/training/update", json={
            "hospital_id": "bad_samples_hospital",
            "model_weights_b64": "",
            "num_samples": 0,
            "training_loss": 0.5,
        }, headers={"X-Node-Token": token})
        assert resp.status_code == 422

    def test_submit_update_rejects_malformed_weights(self, client):
        reg = client.post("/node/register", json={
            "hospital_id": "malformed_weights_hospital",
            "dataset_size": 100,
        })
        token = reg.json()["node_token"]
        resp = client.post("/training/update", json={
            "hospital_id": "malformed_weights_hospital",
            "model_weights_b64": "not-valid-base64-torch-payload",
            "num_samples": 10,
            "training_loss": 0.5,
        }, headers={"X-Node-Token": token})
        assert resp.status_code == 400


class TestBodySizeLimit:
    def test_oversized_request_body_rejected(self, client, monkeypatch):
        # Send an actual 200 MB body just to exercise this would make the
        # test itself slow and memory-heavy for no extra coverage — lower
        # the cap instead and confirm a body past *that* threshold is
        # rejected before it's ever handed to the route.
        import aggregator.server as server_module

        monkeypatch.setattr(server_module, "MAX_TRAINING_UPDATE_BYTES", 100)
        resp = client.post("/training/update", json={
            "hospital_id": "x" * 200,
            "model_weights_b64": "",
            "num_samples": 10,
            "training_loss": 0.5,
        }, headers={"X-Node-Token": "irrelevant"})
        assert resp.status_code == 413


class TestUpdateValidation:
    @staticmethod
    def _register(client, hospital_id):
        resp = client.post("/node/register", json={
            "hospital_id": hospital_id,
            "dataset_size": 100,
        })
        return resp.json()["node_token"]

    def test_register_rejects_non_positive_dataset_size(self, client):
        resp = client.post("/node/register", json={
            "hospital_id": "empty_dataset_hospital",
            "dataset_size": 0,
        })
        assert resp.status_code == 422

    def test_global_model_matches_dp_client_architecture(self, client):
        # Updates from DP clients use the Opacus-fixed model; the server's
        # global model must have identical state_dict keys.
        import aggregator.server as server_module
        from config.settings import USE_DIFFERENTIAL_PRIVACY
        from hospital_node.privacy_layer import make_model_private
        from model.architecture import build_model

        if not USE_DIFFERENTIAL_PRIVACY:
            pytest.skip("DP disabled")
        expected = make_model_private(build_model(pretrained=False)).state_dict().keys()
        assert set(server_module.global_weights.keys()) == set(expected)

    def test_rejects_wrong_shape_and_nan_weights(self, client):
        import aggregator.server as server_module

        token = self._register(client, "bad_tensor_hospital")
        base = server_module.global_weights

        def submit(weights):
            return client.post("/training/update", json={
                "hospital_id": "bad_tensor_hospital",
                "model_weights_b64": server_module._serialize_weights(weights),
                "num_samples": 10,
                "training_loss": 0.5,
            }, headers={"X-Node-Token": token})

        key = next(k for k, v in base.items() if v.is_floating_point() and v.numel() > 1)

        wrong_shape = dict(base)
        wrong_shape[key] = base[key].flatten()[:1].clone()
        assert submit(wrong_shape).status_code == 400

        poisoned = dict(base)
        poisoned[key] = base[key].clone()
        poisoned[key].view(-1)[0] = float("nan")
        assert submit(poisoned).status_code == 400
        assert not any(
            u["hospital_id"] == "bad_tensor_hospital"
            for u in server_module.pending_updates
        )


class TestMetricsAndAdminAccess:
    def test_round_metrics_requires_a_token(self, client):
        assert client.get("/round/metrics").status_code == 403

    def test_round_metrics_with_node_token(self, client):
        token = client.post("/node/register", json={
            "hospital_id": "metrics_node", "dataset_size": 5,
        }).json()["node_token"]
        resp = client.get("/round/metrics", headers={"X-Node-Token": token})
        assert resp.status_code == 200
        assert "metrics" in resp.json()

    def test_admin_token_reads_metrics_and_model(self, client, monkeypatch):
        import aggregator.server as server_module

        monkeypatch.setattr(server_module, "AGGREGATOR_ADMIN_TOKEN", "operator-secret")
        headers = {"X-Node-Token": "operator-secret"}
        assert client.get("/round/metrics", headers=headers).status_code == 200
        assert client.get("/model/latest", headers=headers).status_code == 200
        assert client.get(
            "/model/latest", headers={"X-Node-Token": "wrong"}
        ).status_code == 403

    def test_admin_access_is_off_when_token_unset(self, client, monkeypatch):
        import aggregator.server as server_module

        monkeypatch.setattr(server_module, "AGGREGATOR_ADMIN_TOKEN", "")
        assert client.get("/round/metrics", headers={"X-Node-Token": ""}).status_code == 403


class TestRegistrationControls:
    def test_registration_key_required_when_configured(self, client, monkeypatch):
        import aggregator.server as server_module

        monkeypatch.setattr(server_module, "AGGREGATOR_REGISTRATION_KEY", "join-secret")
        body = {"hospital_id": "keyed_node", "dataset_size": 5}
        assert client.post("/node/register", json=body).status_code == 403
        assert client.post(
            "/node/register", json=body, headers={"X-Registration-Key": "wrong"}
        ).status_code == 403
        ok = client.post(
            "/node/register", json=body, headers={"X-Registration-Key": "join-secret"}
        )
        assert ok.status_code == 200

        # Re-registration is authenticated by the node's own token, not the key.
        again = client.post(
            "/node/register", json=body,
            headers={"X-Node-Token": ok.json()["node_token"]},
        )
        assert again.status_code == 200

    def test_node_cap(self, client, monkeypatch):
        import aggregator.server as server_module

        monkeypatch.setattr(server_module, "AGGREGATOR_MAX_NODES", 0)
        resp = client.post("/node/register", json={"hospital_id": "overflow", "dataset_size": 1})
        assert resp.status_code == 503


class TestConcurrentAggregation:
    def test_concurrent_uploads_aggregate_exactly_once(self, client):
        import threading

        import aggregator.server as server_module

        tokens = {}
        for name in ("conc_a", "conc_b"):
            tokens[name] = client.post(
                "/node/register", json={"hospital_id": name, "dataset_size": 5}
            ).json()["node_token"]

        server_module.pending_updates.clear()
        version_before = server_module.model_version
        payload = server_module._serialize_weights(server_module.global_weights)
        results = {}

        def upload(name):
            results[name] = client.post("/training/update", json={
                "hospital_id": name, "model_weights_b64": payload,
                "num_samples": 5, "training_loss": 0.5,
            }, headers={"X-Node-Token": tokens[name]}).json()

        threads = [threading.Thread(target=upload, args=(n,)) for n in tokens]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(1 for r in results.values() if r["aggregated"]) == 1
        assert server_module.model_version == version_before + 1
        assert server_module.pending_updates == []


class TestHospitalIdValidation:
    @pytest.mark.parametrize("bad", ["", "  ", "a\nb", "has space", "x" * 65, "../etc"])
    def test_register_rejects_unsafe_ids(self, client, bad):
        resp = client.post("/node/register", json={"hospital_id": bad, "dataset_size": 5})
        assert resp.status_code == 422


class TestPersistence:
    def test_state_round_trips_and_mismatch_is_ignored(self, tmp_path, monkeypatch):
        import torch
        import aggregator.server as server_module

        monkeypatch.setattr(server_module, "AGGREGATOR_PERSIST", True)
        monkeypatch.setattr(server_module, "CHECKPOINTS_DIR", tmp_path)
        monkeypatch.setattr(server_module, "_CHECKPOINT_PATH", tmp_path / "g.pt")
        monkeypatch.setattr(server_module, "_META_PATH", tmp_path / "g.json")
        monkeypatch.setattr(server_module, "model_version", 7)

        server_module._persist_state()
        assert (tmp_path / "g.pt").exists()
        assert not list(tmp_path.glob("*.tmp"))

        restored = server_module._load_persisted_state(
            lambda pretrained: server_module.global_weights
        )
        assert restored is not None and restored[1] == 7

        # A checkpoint with a different architecture is not served.
        torch.save({"unrelated": torch.zeros(1)}, tmp_path / "g.pt")
        assert server_module._load_persisted_state(
            lambda pretrained: server_module.global_weights
        ) is None


class TestNodeRegistrationHijack:
    def test_cannot_reregister_without_existing_token(self, client):
        first = client.post("/node/register", json={
            "hospital_id": "hijack_target",
            "dataset_size": 100,
        })
        assert first.status_code == 200

        # An attacker who does not know the issued token cannot steal
        # this hospital_id by re-registering it.
        hijack = client.post("/node/register", json={
            "hospital_id": "hijack_target",
            "dataset_size": 999,
        })
        assert hijack.status_code == 409

    def test_can_reregister_with_existing_token(self, client):
        first = client.post("/node/register", json={
            "hospital_id": "reconnect_node",
            "dataset_size": 100,
        })
        old_token = first.json()["node_token"]

        again = client.post(
            "/node/register",
            json={"hospital_id": "reconnect_node", "dataset_size": 150},
            headers={"X-Node-Token": old_token},
        )
        assert again.status_code == 200

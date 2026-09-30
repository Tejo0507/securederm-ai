"""Tests for the aggregation server API."""

import pytest
from fastapi.testclient import TestClient

from aggregator.server import app


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

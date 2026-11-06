"""The aggregator publishes a SHA-256 of the model it serves, and a node
refuses a download that does not match it."""

import base64
import hashlib
import io
import uuid

import pytest
import torch
from fastapi.testclient import TestClient

from aggregator import server as server_module
from aggregator.server import app
from hospital_node import client as client_module

pytestmark = pytest.mark.federated


def _encode(weights: dict) -> tuple[str, str]:
    buf = io.BytesIO()
    torch.save(weights, buf)
    raw = buf.getvalue()
    return base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest()


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class TestAggregatorPublishesDigest:
    @pytest.fixture
    def token(self):
        with TestClient(app) as client:
            yield client, client.post(
                "/node/register",
                json={"hospital_id": f"digest_{uuid.uuid4().hex[:8]}", "dataset_size": 5},
            ).json()["node_token"]

    def test_digest_matches_the_served_weights(self, token):
        client, node_token = token
        body = client.get("/model/latest", headers={"X-Node-Token": node_token}).json()
        raw = base64.b64decode(body["weights_b64"])
        assert body["weights_sha256"] == hashlib.sha256(raw).hexdigest()

    def test_digest_is_stable_for_a_version_and_follows_new_versions(self, token, monkeypatch):
        client, node_token = token
        headers = {"X-Node-Token": node_token}
        first = client.get("/model/latest", headers=headers).json()
        again = client.get("/model/latest", headers=headers).json()
        assert first["weights_sha256"] == again["weights_sha256"]

        changed = {k: v + 1 if v.is_floating_point() else v
                   for k, v in server_module.global_weights.items()}
        monkeypatch.setattr(server_module, "global_weights", changed)
        monkeypatch.setattr(server_module, "model_version", server_module.model_version + 1)
        newer = client.get("/model/latest", headers=headers).json()
        assert newer["weights_sha256"] != first["weights_sha256"]
        assert newer["weights_sha256"] == hashlib.sha256(
            base64.b64decode(newer["weights_b64"])).hexdigest()


class TestNodeVerifiesDownload:
    def _node(self):
        node = client_module.HospitalClient("node_digest", dataset=[(torch.zeros(3, 4, 4), 0)])
        node.token = "t"
        return node

    def _serve(self, monkeypatch, payload):
        monkeypatch.setattr(client_module.requests, "get", lambda *a, **k: _Response(payload))

    def test_a_matching_digest_is_accepted(self, monkeypatch):
        b64, digest = _encode({"w": torch.arange(3.0)})
        self._serve(monkeypatch, {"model_version": 3, "weights_b64": b64,
                                  "weights_sha256": digest})
        node = self._node()
        weights = node.download_model()
        assert torch.equal(weights["w"], torch.arange(3.0))
        assert node.model_version == 3

    def test_uppercase_digest_is_accepted(self, monkeypatch):
        b64, digest = _encode({"w": torch.zeros(2)})
        self._serve(monkeypatch, {"model_version": 1, "weights_b64": b64,
                                  "weights_sha256": digest.upper()})
        assert self._node().download_model() is not None

    def test_a_tampered_download_is_discarded(self, monkeypatch):
        good_b64, _ = _encode({"w": torch.zeros(2)})
        _, other_digest = _encode({"w": torch.ones(2)})
        self._serve(monkeypatch, {"model_version": 9, "weights_b64": good_b64,
                                  "weights_sha256": other_digest})
        node = self._node()
        assert node.download_model() is None
        assert getattr(node, "model_version", None) != 9   # nothing adopted

    def test_an_older_aggregator_without_a_digest_still_works(self, monkeypatch):
        b64, _ = _encode({"w": torch.zeros(2)})
        self._serve(monkeypatch, {"model_version": 2, "weights_b64": b64})
        assert self._node().download_model() is not None

    def test_garbage_is_still_reported_as_unreadable(self, monkeypatch):
        self._serve(monkeypatch, {"model_version": 2, "weights_b64": "!!not base64!!"})
        assert self._node().download_model() is None

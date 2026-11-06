"""Tests for the aggregator's admin-only GET /nodes."""

import uuid

import pytest
from fastapi.testclient import TestClient

from aggregator import server as server_module
from aggregator.server import app

pytestmark = pytest.mark.federated

ADMIN = "operator-secret-for-tests"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server_module, "AGGREGATOR_ADMIN_TOKEN", ADMIN)
    with TestClient(app) as c:
        yield c


def _register(client, size=25):
    hospital_id = f"nodes_{uuid.uuid4().hex[:8]}"
    token = client.post(
        "/node/register", json={"hospital_id": hospital_id, "dataset_size": size}
    ).json()["node_token"]
    return hospital_id, token


def _admin(client):
    return client.get("/nodes", headers={"X-Node-Token": ADMIN})


def test_anonymous_callers_are_refused(client):
    assert client.get("/nodes").status_code == 403


def test_a_node_token_is_not_enough(client):
    _, node_token = _register(client)
    assert client.get("/nodes", headers={"X-Node-Token": node_token}).status_code == 403


def test_admin_access_is_off_when_no_admin_token_is_configured(client, monkeypatch):
    monkeypatch.setattr(server_module, "AGGREGATOR_ADMIN_TOKEN", "")
    assert client.get("/nodes", headers={"X-Node-Token": ""}).status_code == 403


def test_lists_enrolled_nodes_with_their_declared_size(client):
    hospital_id, _ = _register(client, size=42)
    body = _admin(client).json()
    entry = next(n for n in body["nodes"] if n["hospital_id"] == hospital_id)
    assert entry["dataset_size"] == 42
    assert entry["registered_at"]
    assert entry["update_pending"] is False
    assert body["count"] == len(body["nodes"])


def test_never_exposes_tokens(client):
    _, node_token = _register(client)
    text = _admin(client).text
    assert node_token not in text
    assert "token" not in text.lower()


def test_nodes_are_sorted_by_id(client):
    for _ in range(3):
        _register(client)
    ids = [n["hospital_id"] for n in _admin(client).json()["nodes"]]
    assert ids == sorted(ids)


def test_flags_a_node_with_an_update_waiting(client, monkeypatch):
    hospital_id, _ = _register(client)
    monkeypatch.setattr(
        server_module, "pending_updates",
        [{"hospital_id": hospital_id, "weights": {}, "num_samples": 1, "loss": 0.1}],
    )
    flags = {n["hospital_id"]: n["update_pending"] for n in _admin(client).json()["nodes"]}
    assert flags[hospital_id] is True
    assert sum(flags.values()) == 1

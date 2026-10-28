"""Tests for the aggregator's Prometheus /metrics endpoint."""

import uuid

import pytest
from fastapi.testclient import TestClient

from aggregator import server as server_module
from aggregator.server import app

pytestmark = pytest.mark.federated


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def node_token(client):
    # The aggregator keeps its registry for the life of the process, and a
    # hospital id can only be enrolled once, so every test needs its own.
    return client.post(
        "/node/register",
        json={"hospital_id": f"metrics_{uuid.uuid4().hex[:8]}", "dataset_size": 10},
    ).json()["node_token"]


def _samples(text: str) -> dict[str, float]:
    """Parse exposition text into {metric name: value}, ignoring comments."""
    out = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            name, value = line.split(" ")
            out[name] = float(value)
    return out


class TestMetricsAccess:
    def test_anonymous_callers_are_refused(self, client):
        assert client.get("/metrics").status_code == 403

    def test_wrong_token_is_refused(self, client, node_token):
        assert client.get("/metrics", headers={"X-Node-Token": "nope"}).status_code == 403
        assert client.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code == 403

    def test_node_token_header_is_accepted(self, client, node_token):
        assert client.get("/metrics", headers={"X-Node-Token": node_token}).status_code == 200

    def test_bearer_token_is_accepted_for_prometheus_scrape_configs(self, client, node_token):
        resp = client.get("/metrics", headers={"Authorization": f"Bearer {node_token}"})
        assert resp.status_code == 200

    def test_admin_token_is_accepted(self, client, monkeypatch):
        monkeypatch.setattr(server_module, "AGGREGATOR_ADMIN_TOKEN", "operator-secret")
        resp = client.get("/metrics", headers={"Authorization": "Bearer operator-secret"})
        assert resp.status_code == 200

    def test_non_bearer_authorization_scheme_is_refused(self, client, node_token):
        resp = client.get("/metrics", headers={"Authorization": f"Basic {node_token}"})
        assert resp.status_code == 403


class TestMetricsContent:
    def test_exposition_format(self, client, node_token):
        resp = client.get("/metrics", headers={"X-Node-Token": node_token})
        assert resp.headers["content-type"].startswith("text/plain; version=0.0.4")
        lines = resp.text.splitlines()
        assert resp.text.endswith("\n")
        # Every sample is preceded by its HELP and TYPE lines.
        for i, line in enumerate(lines):
            if not line.startswith("#"):
                name = line.split(" ")[0]
                assert lines[i - 2].startswith(f"# HELP {name} ")
                assert lines[i - 1] == f"# TYPE {name} gauge"

    def test_reports_live_state(self, client, node_token, monkeypatch):
        monkeypatch.setattr(server_module, "model_version", 4)
        monkeypatch.setattr(server_module, "pending_updates", [{}, {}])
        monkeypatch.setattr(
            server_module, "round_metrics",
            [{"round": 1, "nodes": ["a", "b"], "avg_loss": 1.25, "num_nodes": 2},
             {"round": 2, "nodes": ["a", "b", "c"], "avg_loss": 0.5, "num_nodes": 3}],
        )
        samples = _samples(client.get("/metrics", headers={"X-Node-Token": node_token}).text)
        assert samples["securederm_model_version"] == 4
        assert samples["securederm_pending_updates"] == 2
        assert samples["securederm_rounds_completed"] == 2
        assert samples["securederm_last_round_nodes"] == 3
        assert samples["securederm_last_round_avg_loss"] == 0.5
        assert samples["securederm_registered_nodes"] >= 1

    def test_loss_gauge_is_omitted_before_any_round(self, client, node_token, monkeypatch):
        monkeypatch.setattr(server_module, "round_metrics", [])
        samples = _samples(client.get("/metrics", headers={"X-Node-Token": node_token}).text)
        assert "securederm_last_round_avg_loss" not in samples
        assert samples["securederm_rounds_completed"] == 0
        assert samples["securederm_last_round_nodes"] == 0

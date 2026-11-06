"""Tests for GET /api/health/ready."""

import pytest
from fastapi.testclient import TestClient

import web_backend.main as main_module
from model import inference
from web_backend.main import app


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture
def checkpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(inference, "CHECKPOINTS_DIR", tmp_path)
    inference._id_cache.clear()
    yield tmp_path
    inference._id_cache.clear()


def test_ready_when_database_and_model_are_present(client, checkpoints):
    (checkpoints / "global_model.pt").write_bytes(b"weights")
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "checks": {"database": "ok", "model": "ok"}}


def test_degraded_but_serving_without_a_model(client, checkpoints):
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "degraded", "checks": {"database": "ok", "model": "missing"}}


def test_unavailable_when_the_database_is_down(client, checkpoints, monkeypatch):
    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(main_module, "engine", _BrokenEngine())
    resp = client.get("/api/health/ready")
    assert resp.status_code == 503
    assert resp.json()["checks"] == {"database": "down"}
    assert "db down" not in resp.text   # no internals leaked


def test_needs_no_authentication(client, checkpoints):
    assert client.get("/api/health/ready").status_code in (200, 503)

"""Tests for POST /api/training/stop."""

import time

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
from web_backend import auth as auth_module
from web_backend.main import app
from web_backend.routers import training_router


@pytest.fixture(autouse=True)
def _reset_state():
    auth_module._auth_attempts.clear()
    training_router._training_state.clear()
    yield
    for task in list(training_router._running.values()):
        task.cancel()
    auth_module._auth_attempts.clear()
    training_router._training_state.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _wait_until_idle(client, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get("/api/training/status").json()
        if not status["active"]:
            return status
        time.sleep(0.05)
    raise AssertionError("training did not stop in time")


def test_requires_auth_and_csrf(client):
    assert client.post("/api/training/stop").status_code == 401
    sign_in(client, "stop-csrf")
    assert client.post("/api/training/stop").status_code == 403


def test_stopping_when_nothing_runs_is_a_harmless_no_op(client):
    headers, _ = sign_in(client, "stop-idle")
    resp = client.post("/api/training/stop", headers=headers)
    assert resp.status_code == 200 and resp.json() == {"status": "not_running"}


def test_stops_a_running_simulation(client):
    headers, _ = sign_in(client, "stop-run")
    assert client.post("/api/training/start", headers=headers).json()["status"] == "started"
    assert client.get("/api/training/status").json()["active"] is True

    resp = client.post("/api/training/stop", headers=headers)
    assert resp.json()["status"] == "stopping"

    status = _wait_until_idle(client)
    assert status["active"] is False
    assert status["logs"][-1] == "■ Training stopped."
    assert "✓ Federated training complete!" not in status["logs"]


def test_can_start_again_after_stopping(client):
    headers, _ = sign_in(client, "stop-restart")
    client.post("/api/training/start", headers=headers)
    client.post("/api/training/stop", headers=headers)
    _wait_until_idle(client)

    assert client.post("/api/training/start", headers=headers).json()["status"] == "started"
    client.post("/api/training/stop", headers=headers)
    _wait_until_idle(client)


def test_a_stop_while_idle_after_stopping_reports_not_running(client):
    headers, _ = sign_in(client, "stop-twice")
    client.post("/api/training/start", headers=headers)
    client.post("/api/training/stop", headers=headers)
    _wait_until_idle(client)
    assert client.post("/api/training/stop", headers=headers).json() == {"status": "not_running"}


def test_stopping_does_not_touch_another_hospitals_run(client):
    headers, _ = sign_in(client, "stop-mine")
    with TestClient(app, base_url="https://testserver") as other:
        other_headers, _ = sign_in(other, "stop-theirs")
        other.post("/api/training/start", headers=other_headers)

        assert client.post("/api/training/stop", headers=headers).json() == {
            "status": "not_running"
        }
        assert other.get("/api/training/status").json()["active"] is True
        other.post("/api/training/stop", headers=other_headers)
        _wait_until_idle(other)

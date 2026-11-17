"""Starting, stopping and finishing a training run shows up in the account's activity."""

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


def _actions(client):
    return [e["action"] for e in client.get("/api/auth/activity?limit=50").json()]


def _wait_until_idle(client, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not client.get("/api/training/status").json()["active"]:
            return
        time.sleep(0.05)
    raise AssertionError("training did not finish in time")


def test_starting_a_run_is_recorded(client):
    headers, _ = sign_in(client, "audit-start")

    client.post("/api/training/start", headers=headers)

    assert "training_started" in _actions(client)


def test_stopping_a_run_is_recorded_with_its_round(client):
    headers, _ = sign_in(client, "audit-stop")
    client.post("/api/training/start", headers=headers)

    client.post("/api/training/stop", headers=headers)
    _wait_until_idle(client)

    events = client.get("/api/auth/activity").json()
    stopped = [e for e in events if e["action"] == "training_stopped"]
    assert len(stopped) == 1
    assert "round" in stopped[0]


def test_stopping_when_nothing_runs_records_nothing(client):
    headers, _ = sign_in(client, "audit-idle")

    client.post("/api/training/stop", headers=headers)

    assert "training_stopped" not in _actions(client)


def test_a_finished_run_is_recorded(client, monkeypatch):
    async def instant_run(state, hospital_name):
        state["round"] = 5

    monkeypatch.setattr(training_router, "_run_simulation", instant_run)
    headers, _ = sign_in(client, "audit-done")

    client.post("/api/training/start", headers=headers)
    _wait_until_idle(client)

    assert _actions(client)[:2] == ["training_completed", "training_started"]


def test_a_second_start_while_running_is_not_recorded_twice(client):
    headers, _ = sign_in(client, "audit-twice")

    client.post("/api/training/start", headers=headers)
    client.post("/api/training/start", headers=headers)

    assert _actions(client).count("training_started") == 1

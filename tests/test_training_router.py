"""Tests for the training simulation endpoints.

These had zero test coverage before this file existed, and a real bug
with it: /training/status had no auth dependency at all, and the
in-memory state it read from was a single dict shared across every
hospital — whichever hospital most recently clicked "Start Training"
had their name and simulated progress visible to anyone hitting the
endpoint, logged in or not.
"""

import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="securederm_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DB_DIR, 'test.db')}"
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from web_backend.main import app  # noqa: E402
from web_backend import auth as auth_module  # noqa: E402
from web_backend.routers import training_router  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state():
    """Each test gets a clean rate-limit bucket and training-state dict —
    the latter is module-level (in-memory, by design: it models a live
    simulation, not persisted data), so tests must not leak into each
    other through it."""
    auth_module._auth_attempts.clear()
    training_router._training_state.clear()
    yield
    auth_module._auth_attempts.clear()
    training_router._training_state.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _signup_and_verify(client, email, password="correcthorse1", name="Test Hospital"):
    signup = client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": password, "location": "X"},
    )
    token = signup.json()["dev_verification_token"]
    return client.post("/api/auth/verify-email", json={"token": token})


def _csrf_headers(client) -> dict:
    token = client.cookies.get(auth_module.CSRF_COOKIE_NAME)
    return {auth_module.CSRF_HEADER_NAME: token} if token else {}


class TestTrainingStatusAuth:
    def test_status_requires_auth(self, client):
        resp = client.get("/api/training/status")
        assert resp.status_code == 401

    def test_start_requires_auth(self, client):
        resp = client.post("/api/training/start")
        assert resp.status_code == 401


class TestTrainingStateIsolation:
    def test_new_hospital_sees_inactive_state_by_default(self, client):
        _signup_and_verify(client, "freshhospital@example.com", name="Fresh Hospital")
        resp = client.get("/api/training/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False
        assert data["logs"] == []

    def test_one_hospitals_run_is_invisible_to_another(self, client):
        # Hospital A starts a run.
        _signup_and_verify(client, "hospitala@example.com", name="Hospital A Name")
        start = client.post("/api/training/start", headers=_csrf_headers(client))
        assert start.status_code == 200
        status_a = client.get("/api/training/status").json()
        assert status_a["active"] is True
        assert any("Hospital A Name" in log for log in status_a["logs"])

        # Log out of A, sign up as a completely separate Hospital B.
        client.post("/api/auth/logout", headers=_csrf_headers(client))
        _signup_and_verify(client, "hospitalb@example.com", name="Hospital B Name")

        status_b = client.get("/api/training/status")
        assert status_b.status_code == 200
        data_b = status_b.json()
        # This is the actual bug: before the fix, B would see A's
        # "active: true" run and A's hospital name in the logs.
        assert data_b["active"] is False
        assert data_b["logs"] == []
        assert not any("Hospital A Name" in log for log in data_b["logs"])

    def test_starting_while_already_active_does_not_reset_progress(self, client):
        _signup_and_verify(client, "doublestart@example.com", name="Double Start Hospital")
        first = client.post("/api/training/start", headers=_csrf_headers(client))
        assert first.json()["status"] == "started"

        second = client.post("/api/training/start", headers=_csrf_headers(client))
        assert second.json()["status"] == "already_running"

    def test_start_requires_csrf_header(self, client):
        _signup_and_verify(client, "trainingcsrf@example.com")
        resp = client.post("/api/training/start")  # no CSRF header
        assert resp.status_code == 403

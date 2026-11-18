"""Only hospitals that verified their email are part of the network.

A signup that never clicked its verification link is a pending request, not a
member. It must not appear in the directory, and it must not be counted in the
totals the dashboard shows.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.support import PASSWORD, sign_in, unique_email
from web_backend import auth as auth_module
from web_backend.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _pending_signup(name):
    """Register without verifying, from a separate client (no session)."""
    with TestClient(app, base_url="https://testserver") as other:
        resp = other.post(
            "/api/auth/signup",
            json={"name": name, "email": unique_email("pending"), "password": PASSWORD,
                  "location": "Nowhere"},
        )
        assert resp.status_code == 200, resp.text


def _names(client):
    return [h["name"] for h in client.get("/api/hospitals?limit=100&q=Verif%20Probe").json()]


def test_a_pending_signup_is_not_listed(client):
    tag = uuid.uuid4().hex[:6]
    _pending_signup(f"Verif Probe Pending {tag}")
    sign_in(client, "listed", name=f"Verif Probe Member {tag}")

    names = _names(client)

    assert f"Verif Probe Member {tag}" in names
    assert f"Verif Probe Pending {tag}" not in names


def test_network_totals_count_members_only(client):
    sign_in(client, "totals")
    before = client.get("/api/network/stats").json()["hospitals"]

    _pending_signup("Totals Pending")
    unchanged = client.get("/api/network/stats").json()["hospitals"]
    with TestClient(app, base_url="https://testserver") as other:
        sign_in(other, "totals-member")
    grown = client.get("/api/network/stats").json()["hospitals"]

    assert unchanged == before
    assert grown == before + 1


def test_the_total_matches_the_directory(client):
    sign_in(client, "agree")
    _pending_signup("Agree Pending")

    listed = client.get("/api/hospitals?limit=100&offset=0").json()
    total = client.get("/api/network/stats").json()["hospitals"]

    if total <= 100:
        assert len(listed) == total


def test_search_does_not_find_a_pending_signup(client):
    tag = uuid.uuid4().hex[:6]
    _pending_signup(f"Hidden Pending {tag}")
    sign_in(client, "searcher")

    assert client.get(f"/api/hospitals?q=Hidden%20Pending%20{tag}").json() == []

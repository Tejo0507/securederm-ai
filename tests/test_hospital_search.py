"""Tests for the ?q= search on GET /api/hospitals."""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
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


@pytest.fixture
def directory(client):
    """Three hospitals with a run-unique tag so other tests' rows don't interfere."""
    tag = uuid.uuid4().hex[:8]
    for name, location in [
        (f"{tag} Riverside Clinic", "Leeds"),
        (f"{tag} Hilltop Hospital", "Bristol"),
        (f"{tag} 100% Care_Centre", "Leeds"),
    ]:
        with TestClient(app, base_url="https://testserver") as other:
            sign_in(other, "dir", name=name, location=location)
    sign_in(client, "dir-viewer", name=f"{tag} Viewer", location="Nowhere")
    return tag


def _names(client, q):
    return sorted(h["name"] for h in client.get("/api/hospitals", params={"q": q}).json())


def test_matches_name_case_insensitively(client, directory):
    assert _names(client, f"{directory} riverSIDE") == [f"{directory} Riverside Clinic"]


def test_matches_location(client, directory):
    found = _names(client, "Leeds")
    assert {f"{directory} Riverside Clinic", f"{directory} 100% Care_Centre"} <= set(found)
    assert f"{directory} Hilltop Hospital" not in found


def test_no_match_is_an_empty_list(client, directory):
    assert _names(client, f"{directory}-nothing-like-this") == []


def test_blank_query_lists_everyone(client, directory):
    everyone = client.get("/api/hospitals").json()
    assert len(client.get("/api/hospitals", params={"q": "   "}).json()) == len(everyone)


def test_percent_and_underscore_are_literal(client, directory):
    assert _names(client, f"{directory} 100%") == [f"{directory} 100% Care_Centre"]
    assert _names(client, f"{directory} 100% Care_Centre") == [f"{directory} 100% Care_Centre"]
    assert _names(client, f"{directory} 1%e") == []   # % must not act as a wildcard
    assert _names(client, f"{directory} %") == []      # not a wildcard
    assert _names(client, f"{directory} Care_Centr_") == []


def test_returns_only_public_fields(client, directory):
    hit = client.get("/api/hospitals", params={"q": f"{directory} Hilltop"}).json()[0]
    assert set(hit) == {"id", "name", "location"}


def test_combines_with_paging(client, directory):
    page = client.get("/api/hospitals", params={"q": directory, "limit": 2}).json()
    assert len(page) == 2
    rest = client.get("/api/hospitals", params={"q": directory, "limit": 2, "offset": 2}).json()
    assert {h["id"] for h in page}.isdisjoint({h["id"] for h in rest})


def test_overlong_query_is_rejected(client, directory):
    assert client.get("/api/hospitals", params={"q": "x" * 101}).status_code == 422


def test_still_requires_auth():
    with TestClient(app, base_url="https://testserver") as anon:
        assert anon.get("/api/hospitals", params={"q": "a"}).status_code == 401

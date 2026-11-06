"""Tests for GET / DELETE /api/predictions/{id}."""

import pytest
from fastapi.testclient import TestClient

from tests.support import FakeResult, png_bytes, sign_in, use_predictor
from web_backend import auth as auth_module
from web_backend.audit import read_events
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


def _make_predictions(client, headers, count):
    for _ in range(count):
        client.post("/api/predict", headers=headers,
                    files={"file": ("w.png", png_bytes(), "image/png")})
    return [i["id"] for i in client.get("/api/predictions").json()["items"]]


def test_requires_auth(client):
    assert client.get("/api/predictions/1").status_code == 401
    assert client.delete("/api/predictions/1").status_code == 401


def test_fetch_one_entry(client, monkeypatch):
    use_predictor(monkeypatch, FakeResult("Cut", 0.77))
    headers, _ = sign_in(client, "single")
    (entry_id,) = _make_predictions(client, headers, 1)

    body = client.get(f"/api/predictions/{entry_id}").json()
    assert body["id"] == entry_id
    assert body["predicted_class"] == "Cut"
    assert body["confidence"] == pytest.approx(0.77)


def test_unknown_id_is_404(client):
    sign_in(client, "single-missing")
    assert client.get("/api/predictions/999999").status_code == 404


def test_non_numeric_id_is_rejected(client):
    sign_in(client, "single-bad")
    assert client.get("/api/predictions/not-a-number").status_code == 422


def test_other_accounts_entries_look_missing(client, monkeypatch):
    use_predictor(monkeypatch)
    headers, _ = sign_in(client, "single-owner")
    (entry_id,) = _make_predictions(client, headers, 1)

    with TestClient(app, base_url="https://testserver") as other:
        other_headers, _ = sign_in(other, "single-other")
        assert other.get(f"/api/predictions/{entry_id}").status_code == 404
        attempt = other.delete(f"/api/predictions/{entry_id}", headers=other_headers)
        assert attempt.status_code == 404
    assert client.get(f"/api/predictions/{entry_id}").status_code == 200


def test_delete_requires_csrf(client, monkeypatch):
    use_predictor(monkeypatch)
    headers, _ = sign_in(client, "single-csrf")
    (entry_id,) = _make_predictions(client, headers, 1)
    assert client.delete(f"/api/predictions/{entry_id}").status_code == 403


def test_delete_removes_only_that_entry_and_is_audited(client, monkeypatch):
    use_predictor(monkeypatch)
    headers, _ = sign_in(client, "single-delete")
    hospital_id = client.get("/api/auth/me").json()["id"]
    ids = _make_predictions(client, headers, 3)

    resp = client.delete(f"/api/predictions/{ids[0]}", headers=headers)
    assert resp.status_code == 200 and resp.json() == {"deleted_predictions": 1}

    remaining = [i["id"] for i in client.get("/api/predictions").json()["items"]]
    assert remaining == ids[1:]
    assert client.get(f"/api/predictions/{ids[0]}").status_code == 404
    assert read_events(hospital_id)[0]["action"] == "history_entry_erased"


def test_summary_and_export_routes_are_not_shadowed(client):
    sign_in(client, "single-routes")
    assert client.get("/api/predictions/summary").status_code == 200
    assert client.get("/api/predictions/export").status_code == 200

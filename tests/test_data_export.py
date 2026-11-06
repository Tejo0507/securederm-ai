"""Tests for GET /api/auth/export (the account's own data, portable)."""

import json

import pytest
from fastapi.testclient import TestClient

from tests.support import PASSWORD, png_bytes, sign_in, use_predictor
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


def test_requires_auth(client):
    assert client.get("/api/auth/export").status_code == 401


def test_downloads_a_json_attachment(client):
    sign_in(client, "export-basic", name="Export Hospital", location="Leeds")
    resp = client.get("/api/auth/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.json()
    assert body["profile"]["name"] == "Export Hospital"
    assert body["profile"]["location"] == "Leeds"
    assert body["profile"]["email_verified"] is True
    assert set(body) == {"exported_at", "profile", "datasets", "predictions", "activity"}


def test_includes_datasets_predictions_and_activity(client, monkeypatch):
    use_predictor(monkeypatch)
    headers, _ = sign_in(client, "export-full")
    client.post("/api/datasets/upload", headers=headers,
                files={"files": ("a.png", png_bytes((1, 2, 3)), "image/png")})
    for _ in range(2):
        client.post("/api/predict", headers=headers,
                    files={"file": ("w.png", png_bytes(), "image/png")})

    body = client.get("/api/auth/export").json()
    assert body["datasets"][0]["image_count"] == 1
    assert len(body["predictions"]) == 2
    assert body["predictions"][0]["predicted_class"] == "Burns"
    actions = {e["action"] for e in body["activity"]}
    assert {"dataset_upload", "prediction", "email_verified"} <= actions


def test_never_contains_secrets(client):
    headers, email = sign_in(client, "export-secrets")
    text = client.get("/api/auth/export").text
    assert "password" not in text.lower()
    assert PASSWORD not in text
    assert "pbkdf2" not in text
    assert auth_module.CSRF_COOKIE_NAME not in text
    assert client.cookies.get(auth_module.SESSION_COOKIE_NAME) not in text
    assert json.loads(text)["profile"]["email"] == email


def test_only_own_data_is_exported(client, monkeypatch):
    use_predictor(monkeypatch)
    headers, _ = sign_in(client, "export-own")
    client.post("/api/predict", headers=headers,
                files={"file": ("w.png", png_bytes(), "image/png")})

    with TestClient(app, base_url="https://testserver") as other:
        sign_in(other, "export-other", name="Someone Else")
        body = other.get("/api/auth/export").json()
        assert body["predictions"] == []
        assert body["profile"]["name"] == "Someone Else"
        assert all(e["action"] != "prediction" for e in body["activity"])


def test_export_is_audited(client):
    sign_in(client, "export-audit")
    hospital_id = client.get("/api/auth/me").json()["id"]
    client.get("/api/auth/export")
    assert read_events(hospital_id)[0]["action"] == "data_exported"

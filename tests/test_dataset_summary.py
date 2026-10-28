"""Tests for GET /api/datasets/summary."""

import io
import secrets

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from web_backend import auth as auth_module
from web_backend.main import app
from web_backend.routers import hospital_router

# Generated per run: a fixture credential, never a literal in the repo.
TEST_PASSWORD = secrets.token_urlsafe(12)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _sign_in(client, email) -> dict:
    signup = client.post(
        "/api/auth/signup",
        json={"name": "Dataset Hospital", "email": email,
              "password": TEST_PASSWORD, "location": "X"},
    )
    client.post("/api/auth/verify-email", json={"token": signup.json()["dev_verification_token"]})
    return {auth_module.CSRF_HEADER_NAME: client.cookies.get(auth_module.CSRF_COOKIE_NAME)}


def _image(fmt="PNG", color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buf, format=fmt)
    return buf.getvalue()


def _upload(client, headers, *images):
    parts = [("files", (f"i{n}", data, "image/png")) for n, data in enumerate(images)]
    return client.post("/api/datasets/upload", headers=headers, files=parts)


def test_requires_auth(client):
    assert client.get("/api/datasets/summary").status_code == 401


def test_empty_for_a_new_hospital(client):
    _sign_in(client, "dsum1@example.com")
    body = client.get("/api/datasets/summary").json()
    assert body["images"] == 0 and body["total_bytes"] == 0
    assert body["formats"] == {}
    assert body["oldest_upload"] is None and body["newest_upload"] is None
    assert body["quota"] == hospital_router.MAX_IMAGES_PER_HOSPITAL
    assert body["quota_used"] == 0


def test_counts_sizes_and_formats(client):
    headers = _sign_in(client, "dsum2@example.com")
    png_a, png_b, jpg = _image("PNG", (1, 2, 3)), _image("PNG", (9, 9, 9)), _image("JPEG")
    assert _upload(client, headers, png_a, png_b, jpg).json()["uploaded"] == 3

    body = client.get("/api/datasets/summary").json()
    assert body["images"] == 3
    assert body["formats"] == {"png": 2, "jpg": 1}
    assert body["total_bytes"] > 0
    assert body["oldest_upload"] <= body["newest_upload"]
    assert body["quota_used"] == pytest.approx(3 / hospital_router.MAX_IMAGES_PER_HOSPITAL, abs=1e-4)


def test_duplicate_uploads_are_counted_once(client):
    headers = _sign_in(client, "dsum3@example.com")
    same = _image()
    _upload(client, headers, same)
    _upload(client, headers, same)
    assert client.get("/api/datasets/summary").json()["images"] == 1


def test_reflects_erasure(client):
    headers = _sign_in(client, "dsum4@example.com")
    _upload(client, headers, _image())
    client.delete("/api/datasets", headers=headers)
    assert client.get("/api/datasets/summary").json()["images"] == 0


def test_only_counts_own_files(client):
    headers = _sign_in(client, "dsum5a@example.com")
    _upload(client, headers, _image())
    with TestClient(app, base_url="https://testserver") as other:
        _sign_in(other, "dsum5b@example.com")
        assert other.get("/api/datasets/summary").json()["images"] == 0

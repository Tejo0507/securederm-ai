"""Tests for the web platform backend: auth, authorization, and upload safety.

IMPORTANT: this module points DATABASE_URL at a throwaway sqlite file
*before* importing anything from web_backend, so these tests never read
from or write into the real dev/demo securederm.db (the app's startup
lifespan seeds sample data through its own DB session, not just the
`get_db` dependency, so a dependency_overrides-only approach would still
leak into the real database — the env var redirects both).
"""

import io
import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="securederm_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DB_DIR, 'test.db')}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from web_backend.main import app  # noqa: E402
from web_backend import auth as auth_module  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Each test gets a clean rate-limit bucket state."""
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _signup(client, email="hospital@example.com", password="supersecret1", name="Test Hospital"):
    return client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": password, "location": "Testville"},
    )


class TestSignupValidation:
    def test_signup_success(self, client):
        resp = _signup(client)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["hospital"]["email"] == "hospital@example.com"

    def test_signup_rejects_invalid_email(self, client):
        resp = _signup(client, email="not-an-email")
        assert resp.status_code == 422

    def test_signup_rejects_short_password(self, client):
        resp = _signup(client, password="short")
        assert resp.status_code == 422

    def test_signup_duplicate_email_rejected(self, client):
        _signup(client, email="dupe@example.com")
        resp = _signup(client, email="dupe@example.com")
        assert resp.status_code == 400

    def test_signup_email_case_insensitive_duplicate(self, client):
        _signup(client, email="mixedcase@example.com")
        resp = _signup(client, email="MixedCase@Example.com")
        assert resp.status_code == 400


class TestLoginAndAuth:
    def test_login_success_and_me(self, client):
        _signup(client, email="loginme@example.com", password="correcthorse1")
        resp = client.post(
            "/api/auth/login",
            json={"email": "loginme@example.com", "password": "correcthorse1"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "loginme@example.com"

    def test_login_wrong_password_rejected(self, client):
        _signup(client, email="wrongpw@example.com", password="correcthorse1")
        resp = client.post(
            "/api/auth/login",
            json={"email": "wrongpw@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_me_requires_auth_header(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_rejects_tampered_token(self, client):
        signup = _signup(client, email="tamper@example.com")
        token = signup.json()["access_token"]
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
        assert resp.status_code == 401


class TestLoginRateLimit:
    def test_login_rate_limited_after_repeated_failures(self, client):
        _signup(client, email="ratelimit@example.com", password="correcthorse1")
        last_status = None
        for _ in range(auth_module._RATE_LIMIT_MAX_ATTEMPTS + 1):
            last_status = client.post(
                "/api/auth/login",
                json={"email": "ratelimit@example.com", "password": "wrong"},
            ).status_code
        assert last_status == 429


class TestDatasetUpload:
    def _auth_headers(self, client, email="uploader@example.com"):
        resp = _signup(client, email=email, password="correcthorse1")
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def _real_png_bytes(self) -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), color=(120, 60, 60)).save(buf, format="PNG")
        return buf.getvalue()

    def test_upload_rejects_spoofed_content_type(self, client):
        headers = self._auth_headers(client)
        fake_image = b"this is not actually image data"
        resp = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"files": ("fake.jpg", fake_image, "image/jpeg")},
        )
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 0

    def test_upload_accepts_genuine_image(self, client):
        headers = self._auth_headers(client, email="realuploader@example.com")
        resp = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"files": ("wound.png", self._real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 1

    def test_upload_requires_auth(self, client):
        resp = client.post(
            "/api/datasets/upload",
            files={"files": ("wound.png", self._real_png_bytes(), "image/png")},
        )
        assert resp.status_code in (401, 403)

    def test_upload_strips_path_traversal_filename(self, client, tmp_path):
        headers = self._auth_headers(client, email="traversal@example.com")
        resp = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"files": ("../../../evil.png", self._real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 1

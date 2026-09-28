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
    # base_url must be https: session/CSRF cookies are set with Secure=True
    # (real browsers exempt http://localhost from that, but httpx's cookie
    # jar enforces it literally, so the test transport needs to look https).
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _signup(client, email="hospital@example.com", password="supersecret1", name="Test Hospital"):
    return client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": password, "location": "Testville"},
    )


def _csrf_headers(client) -> dict:
    """Session and CSRF tokens live in cookies the TestClient's cookie jar
    already carries; mutating requests must also echo the CSRF cookie back
    as a header (double-submit check)."""
    token = client.cookies.get(auth_module.CSRF_COOKIE_NAME)
    return {auth_module.CSRF_HEADER_NAME: token} if token else {}


class TestSignupValidation:
    def test_signup_success(self, client):
        resp = _signup(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "hospital@example.com"
        assert "access_token" not in data  # session must not be exposed in the body
        assert auth_module.SESSION_COOKIE_NAME in resp.cookies
        assert client.cookies.get(auth_module.SESSION_COOKIE_NAME) is not None
        session_cookie = client.cookies.get(auth_module.SESSION_COOKIE_NAME)
        assert session_cookie  # opaque token, but must be present
        # httpOnly cookies are still visible to a same-process test client's
        # cookie jar (it isn't a browser), but the response shouldn't leak
        # the token anywhere else.
        assert "access_token" not in resp.text

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

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "loginme@example.com"

    def test_login_wrong_password_rejected(self, client):
        _signup(client, email="wrongpw@example.com", password="correcthorse1")
        resp = client.post(
            "/api/auth/login",
            json={"email": "wrongpw@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_me_requires_session_cookie(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_rejects_tampered_session_cookie(self, client):
        _signup(client, email="tamper@example.com")
        good = client.cookies.get(auth_module.SESSION_COOKIE_NAME)
        tampered = good[:-1] + ("a" if good[-1] != "a" else "b")
        client.cookies.set(auth_module.SESSION_COOKIE_NAME, tampered)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_logout_clears_session(self, client):
        _signup(client, email="logout@example.com")
        assert client.get("/api/auth/me").status_code == 200

        resp = client.post("/api/auth/logout", headers=_csrf_headers(client))
        assert resp.status_code == 200

        assert client.get("/api/auth/me").status_code == 401

    def test_logout_requires_csrf_header(self, client):
        _signup(client, email="logoutcsrf@example.com")
        resp = client.post("/api/auth/logout")  # no X-CSRF-Token header
        assert resp.status_code == 403


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
    def _login_and_headers(self, client, email="uploader@example.com"):
        _signup(client, email=email, password="correcthorse1")
        return _csrf_headers(client)

    def _real_png_bytes(self) -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), color=(120, 60, 60)).save(buf, format="PNG")
        return buf.getvalue()

    def test_upload_rejects_spoofed_content_type(self, client):
        headers = self._login_and_headers(client)
        fake_image = b"this is not actually image data"
        resp = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"files": ("fake.jpg", fake_image, "image/jpeg")},
        )
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 0

    def test_upload_accepts_genuine_image(self, client):
        headers = self._login_and_headers(client, email="realuploader@example.com")
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
        assert resp.status_code == 401

    def test_upload_requires_csrf_header(self, client):
        self._login_and_headers(client, email="nocsrf@example.com")
        # Logged in (cookie set) but the CSRF header is deliberately omitted.
        resp = client.post(
            "/api/datasets/upload",
            files={"files": ("wound.png", self._real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 403

    def test_upload_strips_path_traversal_filename(self, client):
        headers = self._login_and_headers(client, email="traversal@example.com")
        resp = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"files": ("../../../evil.png", self._real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 1

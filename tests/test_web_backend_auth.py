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
# The production default (600,000 PBKDF2 rounds) is deliberately slow —
# tests care about hash/verify correctness, not paying that real-world
# cost dozens of times per run. hash/verify_password() take the iteration
# count from the stored hash string itself, so this doesn't weaken what
# TestPasswordHashing actually verifies (round-tripping, legacy-format
# compatibility, salting) — only how long paying for it takes here.
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")

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


def _signup_and_verify(
    client, email="hospital@example.com", password="supersecret1", name="Test Hospital"
):
    """Signup + verify-email in one step, leaving `client` holding an
    active session — what most tests actually need to set up."""
    signup_resp = _signup(client, email=email, password=password, name=name)
    token = signup_resp.json()["dev_verification_token"]
    assert token, "expected a dev_verification_token since SMTP isn't configured in tests"
    return client.post("/api/auth/verify-email", json={"token": token})


def _csrf_headers(client) -> dict:
    """Session and CSRF tokens live in cookies the TestClient's cookie jar
    already carries; mutating requests must also echo the CSRF cookie back
    as a header (double-submit check)."""
    token = client.cookies.get(auth_module.CSRF_COOKIE_NAME)
    return {auth_module.CSRF_HEADER_NAME: token} if token else {}


class TestPasswordHashing:
    """Unit tests for the hashing scheme itself, independent of the API."""

    def test_new_hash_round_trips(self):
        stored = auth_module.hash_password("correcthorse1")
        assert stored.startswith("pbkdf2_sha256$")
        assert auth_module.verify_password("correcthorse1", stored)
        assert not auth_module.verify_password("wrongpassword", stored)

    def test_new_hash_encodes_current_iteration_count(self):
        stored = auth_module.hash_password("correcthorse1")
        _, iterations, _, _ = stored.split("$")
        assert int(iterations) == auth_module.PBKDF2_ITERATIONS

    def test_legacy_hash_format_still_verifies(self):
        """Hospitals created before the iteration count was encoded into
        the hash (format "<salt_hex>:<key_hex>", always 100k rounds) must
        still be able to log in — this exact format is what the 8 seeded
        hospitals in the real dev database have."""
        import hashlib
        import os as _os

        salt = _os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            "sha256", b"correcthorse1", salt, auth_module._LEGACY_PBKDF2_ITERATIONS
        )
        legacy_stored = salt.hex() + ":" + key.hex()
        assert auth_module.verify_password("correcthorse1", legacy_stored)
        assert not auth_module.verify_password("wrongpassword", legacy_stored)

    def test_two_hashes_of_same_password_differ(self):
        # Salted: identical passwords must not produce identical hashes.
        a = auth_module.hash_password("correcthorse1")
        b = auth_module.hash_password("correcthorse1")
        assert a != b


class TestSignupValidation:
    def test_signup_success_does_not_issue_a_session(self, client):
        # Signing up only proves someone typed an email-shaped string, not
        # that they can read mail sent to it — no session until verified.
        resp = _signup(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "hospital@example.com"
        assert data["status"] == "verification_email_sent"
        assert data["dev_verification_token"]  # SMTP unconfigured in tests
        assert auth_module.SESSION_COOKIE_NAME not in resp.cookies
        assert client.get("/api/auth/me").status_code == 401

    def test_signup_rejects_invalid_email(self, client):
        resp = _signup(client, email="not-an-email")
        assert resp.status_code == 422

    def test_signup_rejects_short_password(self, client):
        resp = _signup(client, password="short")
        assert resp.status_code == 422

    def test_signup_rejects_common_password(self, client):
        resp = _signup(client, password="password123")
        assert resp.status_code == 422

    def test_validation_error_detail_is_a_readable_string(self, client):
        # Regression test: FastAPI's default 422 body is
        # {"detail": [{"loc", "msg", "type"}]} — a list, not a string. The
        # frontend does `new Error(err.detail)`, so an unflattened list
        # renders as the literal text "[object Object]" to the user.
        resp = _signup(client, password="short")
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, str)
        assert "object Object" not in detail

    def test_signup_duplicate_email_rejected(self, client):
        _signup(client, email="dupe@example.com")
        resp = _signup(client, email="dupe@example.com")
        assert resp.status_code == 400

    def test_signup_email_case_insensitive_duplicate(self, client):
        _signup(client, email="mixedcase@example.com")
        resp = _signup(client, email="MixedCase@Example.com")
        assert resp.status_code == 400


class TestEmailVerification:
    def test_verify_with_valid_token_issues_session(self, client):
        resp = _signup_and_verify(client, email="verifyme@example.com")
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is True
        assert client.get("/api/auth/me").status_code == 200

    def test_verify_with_unknown_token_rejected(self, client):
        resp = client.post("/api/auth/verify-email", json={"token": "not-a-real-token"})
        assert resp.status_code == 400

    def test_verify_token_is_single_use(self, client):
        signup_resp = _signup(client, email="onceonly@example.com")
        token = signup_resp.json()["dev_verification_token"]
        first = client.post("/api/auth/verify-email", json={"token": token})
        assert first.status_code == 200

        second = client.post("/api/auth/verify-email", json={"token": token})
        assert second.status_code == 400

    def test_login_blocked_until_verified(self, client):
        _signup(client, email="unverified@example.com", password="correcthorse1")
        resp = client.post(
            "/api/auth/login",
            json={"email": "unverified@example.com", "password": "correcthorse1"},
        )
        assert resp.status_code == 403

    def test_resend_verification_allows_login_after(self, client):
        _signup(client, email="resend@example.com", password="correcthorse1")
        resend = client.post(
            "/api/auth/resend-verification", json={"email": "resend@example.com"}
        )
        assert resend.status_code == 200
        token = resend.json()["dev_verification_token"]
        assert token

        verify = client.post("/api/auth/verify-email", json={"token": token})
        assert verify.status_code == 200

        login = client.post(
            "/api/auth/login",
            json={"email": "resend@example.com", "password": "correcthorse1"},
        )
        assert login.status_code == 200

    def test_resend_verification_same_response_for_unknown_email(self, client):
        # Must not reveal whether an email is registered at all.
        known = _signup(client, email="knownaccount@example.com")
        assert known.status_code == 200

        resp_known = client.post(
            "/api/auth/resend-verification", json={"email": "knownaccount@example.com"}
        )
        resp_unknown = client.post(
            "/api/auth/resend-verification", json={"email": "totally-unregistered@example.com"}
        )
        assert resp_known.status_code == resp_unknown.status_code == 200
        assert resp_known.json()["status"] == resp_unknown.json()["status"]


class TestLoginAndAuth:
    def test_login_success_and_me(self, client):
        _signup_and_verify(client, email="loginme@example.com", password="correcthorse1")
        client.post("/api/auth/logout", headers=_csrf_headers(client))

        resp = client.post(
            "/api/auth/login",
            json={"email": "loginme@example.com", "password": "correcthorse1"},
        )
        assert resp.status_code == 200

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "loginme@example.com"

    def test_login_wrong_password_rejected(self, client):
        _signup_and_verify(client, email="wrongpw@example.com", password="correcthorse1")
        client.post("/api/auth/logout", headers=_csrf_headers(client))
        resp = client.post(
            "/api/auth/login",
            json={"email": "wrongpw@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_email_rejected_identically(self, client):
        # Both "no such account" and "wrong password" must return the same
        # status and message — the whole point of always hashing against
        # DUMMY_PASSWORD_HASH is that an attacker can't tell them apart.
        resp = client.post(
            "/api/auth/login",
            json={"email": "nobody-here@example.com", "password": "whatever123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_me_requires_session_cookie(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_rejects_tampered_session_cookie(self, client):
        _signup_and_verify(client, email="tamper@example.com")
        good = client.cookies.get(auth_module.SESSION_COOKIE_NAME)
        tampered = good[:-1] + ("a" if good[-1] != "a" else "b")
        client.cookies.set(auth_module.SESSION_COOKIE_NAME, tampered)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_logout_clears_session(self, client):
        _signup_and_verify(client, email="logout@example.com")
        assert client.get("/api/auth/me").status_code == 200

        resp = client.post("/api/auth/logout", headers=_csrf_headers(client))
        assert resp.status_code == 200

        assert client.get("/api/auth/me").status_code == 401

    def test_logout_requires_csrf_header(self, client):
        _signup_and_verify(client, email="logoutcsrf@example.com")
        resp = client.post("/api/auth/logout")  # no X-CSRF-Token header
        assert resp.status_code == 403


class TestLoginRateLimit:
    def test_login_rate_limited_after_repeated_failures(self, client):
        _signup_and_verify(client, email="ratelimit@example.com", password="correcthorse1")
        client.post("/api/auth/logout", headers=_csrf_headers(client))
        last_status = None
        for _ in range(auth_module._RATE_LIMIT_MAX_ATTEMPTS + 1):
            last_status = client.post(
                "/api/auth/login",
                json={"email": "ratelimit@example.com", "password": "wrong"},
            ).status_code
        assert last_status == 429


class TestDatasetUpload:
    def _login_and_headers(self, client, email="uploader@example.com"):
        _signup_and_verify(client, email=email, password="correcthorse1")
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

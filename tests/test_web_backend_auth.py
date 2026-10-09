"""Tests for the web platform backend: auth, authorization, and upload safety.

DATABASE_URL/PBKDF2_ITERATIONS test isolation is set centrally in
conftest.py, before this file (or anything it imports) is ever
collected — see that file for why it has to be centralized rather than
each test file guarding its own import.
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from web_backend.main import app
from web_backend import auth as auth_module


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


pytestmark = pytest.mark.security


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

    def test_logout_clears_cookies_even_when_session_is_invalid(self, client):
        # An expired/revoked session used to get a 401 here, so the stale
        # cookies could never be cleared from the browser.
        client.cookies.set(auth_module.SESSION_COOKIE_NAME, "expired.or.garbage")
        client.cookies.set(auth_module.CSRF_COOKIE_NAME, "csrf-value")
        resp = client.post(
            "/api/auth/logout", headers={auth_module.CSRF_HEADER_NAME: "csrf-value"}
        )
        assert resp.status_code == 200
        assert client.get("/api/auth/me").status_code == 401

    def test_logout_without_any_session_is_a_harmless_noop(self, client):
        assert client.post("/api/auth/logout").status_code == 200


class TestSessionRevocation:
    def test_logged_out_token_cannot_be_replayed(self, client):
        _signup_and_verify(client, email="replay@example.com")
        stolen = client.cookies.get(auth_module.SESSION_COOKIE_NAME)
        assert client.get("/api/auth/me").status_code == 200

        assert client.post("/api/auth/logout", headers=_csrf_headers(client)).status_code == 200

        # Someone who copied the cookie before logout presents it again.
        client.cookies.set(auth_module.SESSION_COOKIE_NAME, stolen)
        assert client.get("/api/auth/me").status_code == 401

    def test_other_sessions_stay_valid(self, client):
        _signup_and_verify(client, email="keepA@example.com")
        a_cookie = client.cookies.get(auth_module.SESSION_COOKIE_NAME)
        _signup_and_verify(client, email="keepB@example.com")
        client.post("/api/auth/logout", headers=_csrf_headers(client))
        client.cookies.set(auth_module.SESSION_COOKIE_NAME, a_cookie)
        assert client.get("/api/auth/me").status_code == 200


class TestChangePassword:
    def test_changes_password_and_ends_the_session(self, client):
        _signup_and_verify(client, email="chgpw@example.com", password="correcthorse1")
        resp = client.post(
            "/api/auth/change-password", headers=_csrf_headers(client),
            json={"current_password": "correcthorse1", "new_password": "batterystaple9"},
        )
        assert resp.status_code == 200
        assert client.get("/api/auth/me").status_code == 401
        email = "chgpw@example.com"
        old = client.post("/api/auth/login", json={"email": email, "password": "correcthorse1"})
        new = client.post("/api/auth/login", json={"email": email, "password": "batterystaple9"})
        assert old.status_code == 401 and new.status_code == 200

    def test_wrong_current_password_rejected(self, client):
        _signup_and_verify(client, email="chgpw2@example.com", password="correcthorse1")
        resp = client.post(
            "/api/auth/change-password", headers=_csrf_headers(client),
            json={"current_password": "nope-nope-nope", "new_password": "batterystaple9"},
        )
        assert resp.status_code == 401

    def test_requires_csrf(self, client):
        _signup_and_verify(client, email="chgpw3@example.com", password="correcthorse1")
        resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "correcthorse1", "new_password": "batterystaple9"},
        )
        assert resp.status_code == 403


class TestDataErasure:
    def _png(self, color=(1, 2, 3)):
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), color=color).save(buf, format="PNG")
        return buf.getvalue()

    def test_delete_datasets_removes_files_and_records(self, client):
        from web_backend.routers import hospital_router

        _signup_and_verify(client, email="erase@example.com")
        headers = _csrf_headers(client)
        client.post("/api/datasets/upload", headers=headers,
                    files={"files": ("a.png", self._png(), "image/png")})
        hospital_id = client.get("/api/auth/me").json()["id"]
        assert any((hospital_router.UPLOAD_DIR / str(hospital_id)).iterdir())

        resp = client.delete("/api/datasets", headers=headers)
        assert resp.status_code == 200 and resp.json()["deleted_images"] == 1
        assert not (hospital_router.UPLOAD_DIR / str(hospital_id)).exists()
        assert client.get("/api/datasets").json() == []

    def test_delete_datasets_requires_csrf(self, client):
        _signup_and_verify(client, email="erase2@example.com")
        assert client.delete("/api/datasets").status_code == 403

    def test_delete_account_needs_password_and_removes_everything(self, client):
        from web_backend.routers import hospital_router

        _signup_and_verify(client, email="bye@example.com", password="correcthorse1")
        headers = _csrf_headers(client)
        client.post("/api/datasets/upload", headers=headers,
                    files={"files": ("a.png", self._png(), "image/png")})
        hospital_id = client.get("/api/auth/me").json()["id"]

        wrong = client.request("DELETE", "/api/auth/account", headers=headers,
                               json={"password": "wrong-password"})
        assert wrong.status_code == 401
        assert client.get("/api/auth/me").status_code == 200

        ok = client.request("DELETE", "/api/auth/account", headers=headers,
                            json={"password": "correcthorse1"})
        assert ok.status_code == 200
        assert not (hospital_router.UPLOAD_DIR / str(hospital_id)).exists()
        assert client.get("/api/auth/me").status_code == 401
        login = client.post("/api/auth/login",
                            json={"email": "bye@example.com", "password": "correcthorse1"})
        assert login.status_code == 401


class TestResendCooldown:
    def test_second_resend_for_same_address_is_throttled(self, client):
        from web_backend.routers import auth_router

        auth_router._last_resend.clear()
        signup = _signup(client, email="spamtarget@example.com")
        assert signup.status_code == 200
        body = {"email": "spamtarget@example.com"}
        first = client.post("/api/auth/resend-verification", json=body)
        second = client.post("/api/auth/resend-verification", json=body)
        # Same public response either way (no enumeration), but only the
        # first issues a token.
        assert first.json()["status"] == second.json()["status"]
        assert first.json()["dev_verification_token"]
        assert second.json()["dev_verification_token"] is None


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


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, host):
        self.client = _FakeClient(host)


class TestRateLimitMemory:
    """Unit tests directly against the rate limiter's bookkeeping — not
    the HTTP layer, since what's under test here is a memory-leak bug:
    _auth_attempts gained one permanent entry for every distinct
    (bucket, client IP) pair ever seen and never removed it, even for a
    client that hits the endpoint once and never returns (so a fix that
    only prunes on that same key's next lookup wouldn't actually help
    the common case — this one does a full sweep instead)."""

    def test_sweep_removes_only_genuinely_stale_entries(self):
        now = auth_module.time.time()
        stale_key = "login:198.51.100.7"
        fresh_key = "login:203.0.113.9"
        auth_module._auth_attempts[stale_key].append(
            now - auth_module._RATE_LIMIT_WINDOW_SECONDS - 1
        )
        auth_module._auth_attempts[fresh_key].append(now)

        auth_module._sweep_expired_rate_limit_entries(now)

        assert stale_key not in auth_module._auth_attempts
        assert fresh_key in auth_module._auth_attempts

        auth_module._auth_attempts.pop(fresh_key, None)

    def test_a_client_that_never_returns_is_eventually_forgotten(self):
        # The actual regression this guards against: with the old code,
        # a one-off prober that calls the endpoint exactly once and
        # never comes back left a permanent entry — nothing was ever
        # looked up again for that key to trigger cleanup. The periodic
        # sweep is the only thing that can catch this case.
        key = "login:192.0.2.55"
        auth_module._auth_attempts.pop(key, None)
        auth_module.enforce_auth_rate_limit(_FakeRequest("192.0.2.55"), "login")
        assert key in auth_module._auth_attempts

        later = auth_module.time.time() + auth_module._RATE_LIMIT_WINDOW_SECONDS + 1
        auth_module._sweep_expired_rate_limit_entries(later)

        assert key not in auth_module._auth_attempts


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

    def test_reuploading_same_filename_does_not_inflate_the_count(self, client):
        # Regression test: image_count used to be incremented by however
        # many files were accepted in a request, so uploading a file whose
        # name collides with one already on disk (it overwrites, not
        # adds) would count it twice — total_images could climb past the
        # actual number of files sitting in the hospital's directory.
        headers = self._login_and_headers(client, email="reupload@example.com")

        first = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"files": ("dup.png", self._real_png_bytes(), "image/png")},
        )
        assert first.json()["total_images"] == 1

        second = client.post(
            "/api/datasets/upload",
            headers=headers,
            files={"files": ("dup.png", self._real_png_bytes(), "image/png")},
        )
        assert second.json()["uploaded"] == 1  # the request did accept a file...
        assert second.json()["total_images"] == 1  # ...but it overwrote, not added

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


class TestUploadFilenameEdgeCases:
    def _png(self) -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, format="PNG")
        return buf.getvalue()

    @pytest.mark.parametrize("idx,name", [(0, ".."), (1, "."), (2, "..\\..\\evil.png")])
    def test_odd_filenames_never_500_or_escape(self, client, idx, name):
        _signup_and_verify(client, email=f"oddname{idx}@example.com", password="correcthorse1")
        resp = client.post(
            "/api/datasets/upload",
            headers=_csrf_headers(client),
            files={"files": (name, self._png(), "image/png")},
        )
        assert resp.status_code == 200
        # The client's filename is never used for storage, so odd names are
        # harmless: the image is accepted and saved under a hash-derived name.
        assert resp.json()["uploaded"] == 1


class TestNetworkListingsRequireAuth:
    @pytest.mark.parametrize(
        "path", ["/api/hospitals", "/api/federated/rounds", "/api/training/metrics"]
    )
    def test_network_data_is_not_public(self, client, path):
        # These list other hospitals' names/locations and who took part in
        # each round; they were readable by anyone on the internet.
        assert client.get(path).status_code == 401

    def test_models_marketplace_stays_public(self, client):
        assert client.get("/api/models").status_code == 200


class TestUploadQuota:
    def test_upload_stops_at_the_per_hospital_cap(self, client, monkeypatch):
        from web_backend.routers import hospital_router

        monkeypatch.setattr(hospital_router, "MAX_IMAGES_PER_HOSPITAL", 1)
        _signup_and_verify(client, email="quota@example.com", password="correcthorse1")

        def png(color):
            buf = io.BytesIO()
            Image.new("RGB", (8, 8), color=color).save(buf, format="PNG")
            return buf.getvalue()

        headers = _csrf_headers(client)

        first = client.post("/api/datasets/upload", headers=headers,
                            files={"files": ("one.png", png((1, 2, 3)), "image/png")})
        assert first.status_code == 200
        second = client.post("/api/datasets/upload", headers=headers,
                             files={"files": ("two.png", png((9, 9, 9)), "image/png")})
        assert second.status_code == 413
        # Re-sending an image already stored doesn't add to the count.
        again = client.post("/api/datasets/upload", headers=headers,
                            files={"files": ("one.png", png((1, 2, 3)), "image/png")})
        assert again.status_code == 200 and again.json()["total_images"] == 1

    def test_partial_batch_is_saved_and_count_stays_accurate(self, client, monkeypatch):
        from web_backend.routers import hospital_router

        monkeypatch.setattr(hospital_router, "MAX_IMAGES_PER_HOSPITAL", 2)
        _signup_and_verify(client, email="quota2@example.com", password="correcthorse1")
        files = []
        for i in range(4):
            buf = io.BytesIO()
            Image.new("RGB", (8, 8), color=(i * 40, 0, 0)).save(buf, format="PNG")
            files.append(("files", (f"{i}.png", buf.getvalue(), "image/png")))
        resp = client.post("/api/datasets/upload", headers=_csrf_headers(client), files=files)
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 2
        assert resp.json()["total_images"] == 2
        assert resp.json()["quota_reached"] is True


class TestUploadPrivacy:
    def _jpeg_with_exif(self) -> bytes:
        exif = Image.Exif()
        exif[0x010F] = "SecretCameraMaker"      # Make
        exif[0x013B] = "Dr. Patient Name"       # Artist
        buf = io.BytesIO()
        Image.new("RGB", (16, 16), color=(200, 100, 90)).save(buf, format="JPEG", exif=exif)
        return buf.getvalue()

    def test_sanitize_removes_exif_and_keeps_pixels(self):
        from web_backend.image_validation import sanitize_image

        original = self._jpeg_with_exif()
        assert b"SecretCameraMaker" in original
        clean, ext = sanitize_image(original)
        assert ext == ".jpg"
        assert b"SecretCameraMaker" not in clean and b"Dr. Patient Name" not in clean
        with Image.open(io.BytesIO(clean)) as img:
            assert img.size == (16, 16)
            assert len(img.getexif()) == 0

    def test_png_text_chunks_are_removed(self):
        from PIL.PngImagePlugin import PngInfo
        from web_backend.image_validation import sanitize_image

        info = PngInfo()
        info.add_text("PatientName", "Jane Doe")
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, format="PNG", pnginfo=info)
        assert b"Jane Doe" in buf.getvalue()
        clean, _ = sanitize_image(buf.getvalue())
        assert b"Jane Doe" not in clean

    def test_uploaded_file_is_stored_clean_and_without_the_client_filename(self, client):
        from web_backend.routers import hospital_router

        _signup_and_verify(client, email="privacyup@example.com", password="correcthorse1")
        resp = client.post(
            "/api/datasets/upload",
            headers=_csrf_headers(client),
            files={"files": ("JANE_DOE_MRN12345.jpg", self._jpeg_with_exif(), "image/jpeg")},
        )
        assert resp.json()["uploaded"] == 1

        stored = [
            p for d in hospital_router.UPLOAD_DIR.iterdir() if d.is_dir()
            for p in d.iterdir()
            if b"SecretCameraMaker" in p.read_bytes() or "JANE" in p.name
        ]
        assert stored == []


class TestUploadedImageLimits:
    def test_decompression_bomb_is_rejected_cleanly(self, client):
        from PIL import Image as PILImage
        from web_backend import image_validation

        buf = io.BytesIO()
        PILImage.new("1", (9000, 9000)).save(buf, format="PNG")  # tiny file, 81M pixels
        assert len(buf.getvalue()) < 100_000
        assert image_validation.is_genuine_image(buf.getvalue()) is False

    def test_normal_image_still_accepted(self):
        from PIL import Image as PILImage
        from web_backend import image_validation

        buf = io.BytesIO()
        PILImage.new("RGB", (64, 64)).save(buf, format="PNG")
        assert image_validation.is_genuine_image(buf.getvalue()) is True


class TestListEndpointPagination:
    @pytest.fixture(autouse=True)
    def _signed_in(self, client, request):
        # Unique per test: the database persists across tests in a run.
        _signup_and_verify(
            client, email=f"pager-{request.node.name}@example.com", password="correcthorse1"
        )

    def test_hospitals_default_and_capped_page_size(self, client):
        for i in range(5):
            _signup(client, email=f"pageuser{i}@example.com")

        default_page = client.get("/api/hospitals")
        assert default_page.status_code == 200
        assert len(default_page.json()) >= 5  # default limit (50) comfortably covers this

        small_page = client.get("/api/hospitals?limit=2")
        assert small_page.status_code == 200
        assert len(small_page.json()) == 2

    def test_hospitals_offset_moves_the_window(self, client):
        for i in range(5):
            _signup(client, email=f"offsetuser{i}@example.com")

        page1 = client.get("/api/hospitals?limit=2&offset=0").json()
        page2 = client.get("/api/hospitals?limit=2&offset=2").json()
        assert [h["id"] for h in page1] != [h["id"] for h in page2]

    def test_hospitals_rejects_page_size_over_the_cap(self, client):
        resp = client.get("/api/hospitals?limit=1000")
        assert resp.status_code == 422

    def test_hospitals_rejects_negative_offset(self, client):
        resp = client.get("/api/hospitals?offset=-1")
        assert resp.status_code == 422

    def test_models_respects_limit(self, client):
        resp = client.get("/api/models?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

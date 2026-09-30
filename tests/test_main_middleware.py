"""Tests for the app-level middleware and exception handlers in
web_backend/main.py: security headers, the request body size cap, and
the global exception handler that hides internal error details.

These were added in an earlier hardening pass and, until now, were only
ever verified by manually curling a running server once — nothing in CI
would have caught a future change silently breaking any of them.
"""

import pytest
from fastapi.testclient import TestClient

import web_backend.main as main_module
from web_backend.database import get_db
from web_backend.main import app


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


class TestSecurityHeaders:
    def test_security_headers_present_on_every_response(self, client):
        resp = client.get("/api/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert (
            resp.headers["Content-Security-Policy"]
            == "default-src 'none'; frame-ancestors 'none'"
        )

    def test_hsts_only_set_in_production(self, client, monkeypatch):
        monkeypatch.setattr(main_module, "IS_PRODUCTION", False)
        assert "Strict-Transport-Security" not in client.get("/api/health").headers

        monkeypatch.setattr(main_module, "IS_PRODUCTION", True)
        assert "Strict-Transport-Security" in client.get("/api/health").headers


class TestBodySizeLimit:
    def test_oversized_request_body_rejected(self, client, monkeypatch):
        # A real 25 MB request would make this test slow and memory-heavy
        # for no extra coverage — lower the cap instead and confirm a body
        # past *that* threshold is rejected before reaching any route.
        monkeypatch.setattr(main_module, "MAX_REQUEST_BODY_BYTES", 10)
        resp = client.post(
            "/api/auth/login",
            json={"email": "someone@example.com", "password": "whatever123"},
        )
        assert resp.status_code == 413

    def test_normal_sized_request_not_rejected(self, client, monkeypatch):
        monkeypatch.setattr(main_module, "MAX_REQUEST_BODY_BYTES", 10 * 1024 * 1024)
        resp = client.post(
            "/api/auth/login",
            json={"email": "someone@example.com", "password": "whatever123"},
        )
        # Rejected for being wrong credentials, not for size.
        assert resp.status_code == 401


class TestUnhandledExceptionHandler:
    def test_unexpected_error_returns_generic_500_not_internals(self):
        def _broken_get_db():
            raise RuntimeError("simulated database outage: connection refused on 10.0.0.5")
            yield  # pragma: no cover - unreachable, keeps this a generator

        app.dependency_overrides[get_db] = _broken_get_db
        try:
            # TestClient defaults to raise_server_exceptions=True, which
            # re-raises an unhandled exception into the *test* instead of
            # letting the app's registered handler produce a response —
            # exactly the thing this test needs to observe, so it has to
            # be turned off here specifically.
            with TestClient(
                app, base_url="https://testserver", raise_server_exceptions=False
            ) as isolated_client:
                resp = isolated_client.get("/api/models")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 500
        body = resp.json()
        assert body == {"detail": "Internal server error."}
        assert "RuntimeError" not in resp.text
        assert "10.0.0.5" not in resp.text
        assert "simulated database outage" not in resp.text

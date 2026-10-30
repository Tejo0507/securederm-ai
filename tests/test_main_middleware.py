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


class TestHealthCheck:
    def test_healthy_when_database_reachable(self, client):
        assert client.get("/api/health").json()["status"] == "ok"

    def test_reports_503_when_database_is_down(self, client, monkeypatch):
        import web_backend.main as main_module

        class _BrokenEngine:
            def connect(self):
                raise RuntimeError("db down")

        monkeypatch.setattr(main_module, "engine", _BrokenEngine())
        resp = client.get("/api/health")
        assert resp.status_code == 503
        assert resp.json() == {"status": "unavailable"}  # no internals leaked


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


class TestRequestId:
    def test_every_response_gets_an_id(self, client):
        first = client.get("/api/health").headers["X-Request-ID"]
        second = client.get("/api/health").headers["X-Request-ID"]
        assert len(first) == 32 and first != second

    def test_a_well_formed_caller_id_is_reused(self, client):
        resp = client.get("/api/health", headers={"X-Request-ID": "proxy-req-12345"})
        assert resp.headers["X-Request-ID"] == "proxy-req-12345"

    @pytest.mark.parametrize("bad", ["short", "has spaces in it!!", "x" * 65, "new\tline-id-ok"])
    def test_a_malformed_caller_id_is_replaced(self, client, bad):
        resp = client.get("/api/health", headers={"X-Request-ID": bad})
        assert resp.headers["X-Request-ID"] != bad
        assert len(resp.headers["X-Request-ID"]) == 32

    def test_rejected_oversized_requests_still_carry_an_id(self, client, monkeypatch):
        monkeypatch.setattr(main_module, "MAX_REQUEST_BODY_BYTES", 10)
        resp = client.post("/api/auth/login", json={"email": "a@example.com", "password": "pw"})
        assert resp.status_code == 413
        assert resp.headers["X-Request-ID"]

    def test_the_id_is_exposed_to_browsers_via_cors(self, client):
        resp = client.get(
            "/api/health", headers={"Origin": "http://localhost:3000"}
        )
        assert "X-Request-ID" in resp.headers["access-control-expose-headers"]

    def test_log_records_carry_the_id(self):
        import logging

        from web_backend.request_id import RequestIdFilter, set_request_id

        set_request_id("log-test-id-123")
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
        RequestIdFilter().filter(record)
        assert record.request_id == "log-test-id-123"

    def test_server_errors_carry_the_id_too(self):
        def _broken_get_db():
            raise RuntimeError("boom")
            yield  # pragma: no cover

        app.dependency_overrides[get_db] = _broken_get_db
        try:
            with TestClient(
                app, base_url="https://testserver", raise_server_exceptions=False
            ) as isolated:
                resp = isolated.get("/api/models", headers={"X-Request-ID": "trace-me-0001"})
        finally:
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 500
        assert resp.headers["X-Request-ID"] == "trace-me-0001"


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

    def test_rejection_is_readable_by_the_browser_frontend(self, client, monkeypatch):
        # The frontend is a different origin from the API. A 413 that leaves
        # without CORS headers is hidden by the browser, which then reports a
        # generic network failure instead of "Request body too large."
        monkeypatch.setattr(main_module, "MAX_REQUEST_BODY_BYTES", 10)
        resp = client.post(
            "/api/auth/login",
            json={"email": "someone@example.com", "password": "whatever123"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 413
        assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert resp.headers["access-control-allow-credentials"] == "true"
        assert resp.headers["X-Request-ID"]   # still tagged, and still has security headers
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

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

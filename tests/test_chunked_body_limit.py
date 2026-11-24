"""The request size limit must also apply to bodies sent without a length.

Passing an iterator as the content makes the client use chunked transfer
encoding, so no Content-Length header reaches the server.
"""

import pytest
from fastapi.testclient import TestClient

import aggregator.server as aggregator
import web_backend.main as web
from web_backend import auth as auth_module

pytestmark = pytest.mark.security

LIMIT = 4096


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


def _chunks(total: int, size: int = 1024):
    for _ in range(total // size):
        yield b"x" * size


def test_web_backend_refuses_an_oversized_chunked_body(monkeypatch):
    monkeypatch.setattr(web, "MAX_REQUEST_BODY_BYTES", LIMIT)
    with TestClient(web.app, base_url="https://testserver") as client:
        resp = client.post(
            "/api/auth/login",
            content=_chunks(LIMIT * 4),
            headers={"Content-Type": "application/json", "Origin": "http://localhost:3000"},
        )

    assert "content-length" not in resp.request.headers
    assert resp.status_code == 413
    assert resp.json()["detail"] == "Request body too large."
    # The browser must be able to read the error, so CORS and security headers apply.
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_web_backend_refuses_an_oversized_chunked_upload(monkeypatch):
    monkeypatch.setattr(web, "MAX_REQUEST_BODY_BYTES", LIMIT)

    def multipart():
        yield (b"--b\r\nContent-Disposition: form-data; name=\"files\"; "
               b"filename=\"a.png\"\r\nContent-Type: image/png\r\n\r\n")
        yield from _chunks(LIMIT * 4)
        yield b"\r\n--b--\r\n"

    with TestClient(web.app, base_url="https://testserver") as client:
        resp = client.post(
            "/api/datasets/upload",
            content=multipart(),
            headers={"Content-Type": "multipart/form-data; boundary=b"},
        )

    assert resp.status_code == 413


def test_web_backend_accepts_a_small_chunked_body():
    with TestClient(web.app, base_url="https://testserver") as client:
        resp = client.post(
            "/api/auth/login",
            content=iter([b'{"email": "nobody@example.com", ', b'"password": "x"}']),
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 401   # parsed normally, just not a real account


def test_aggregator_refuses_an_oversized_chunked_body(monkeypatch):
    monkeypatch.setattr(aggregator, "MAX_TRAINING_UPDATE_BYTES", LIMIT)
    # No lifespan: the request is refused before the global model is needed.
    client = TestClient(aggregator.app)

    resp = client.post(
        "/training/update",
        content=_chunks(LIMIT * 4),
        headers={"Content-Type": "application/json", "X-Node-Token": "t"},
    )

    assert resp.status_code == 413

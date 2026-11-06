"""Tests for the X-RateLimit-* headers on the prediction endpoints."""

import pytest
from fastapi.testclient import TestClient

from tests.support import png_bytes, sign_in, use_predictor
from web_backend import auth as auth_module
from web_backend.main import app

LIMIT_SETTING = "web_backend.routers.predict_router.PREDICT_RATE_LIMIT_PER_MINUTE"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _predict(client, headers):
    return client.post(
        "/api/predict", headers=headers, files={"file": ("w.png", png_bytes(), "image/png")}
    )


def test_remaining_quota_counts_down(client, monkeypatch):
    use_predictor(monkeypatch)
    monkeypatch.setattr(LIMIT_SETTING, 3)
    headers, _ = sign_in(client, "quota")

    remaining = []
    for _ in range(3):
        resp = _predict(client, headers)
        assert resp.headers["x-ratelimit-limit"] == "3"
        remaining.append(int(resp.headers["x-ratelimit-remaining"]))
    assert remaining == [2, 1, 0]


def test_batch_consumes_one_unit_per_image(client, monkeypatch):
    use_predictor(monkeypatch)
    monkeypatch.setattr(LIMIT_SETTING, 10)
    headers, _ = sign_in(client, "quota-batch")
    parts = [("files", (f"{i}.png", png_bytes(), "image/png")) for i in range(4)]
    resp = client.post("/api/predict/batch", headers=headers, files=parts)
    assert resp.status_code == 200
    assert resp.headers["x-ratelimit-remaining"] == "6"


def test_blocked_request_reports_zero_remaining(client, monkeypatch):
    use_predictor(monkeypatch)
    monkeypatch.setattr(LIMIT_SETTING, 1)
    headers, _ = sign_in(client, "quota-blocked")
    _predict(client, headers)
    blocked = _predict(client, headers)
    assert blocked.status_code == 429
    assert blocked.headers["x-ratelimit-limit"] == "1"
    assert blocked.headers["x-ratelimit-remaining"] == "0"
    assert int(blocked.headers["retry-after"]) >= 1


def test_no_headers_when_the_limit_is_disabled(client, monkeypatch):
    use_predictor(monkeypatch)
    monkeypatch.setattr(LIMIT_SETTING, 0)
    headers, _ = sign_in(client, "quota-off")
    resp = _predict(client, headers)
    assert resp.status_code == 200
    assert "x-ratelimit-remaining" not in resp.headers


def test_limiter_return_value():
    auth_module._auth_attempts.clear()
    assert auth_module.enforce_account_rate_limit(1, "t", 5) == 4
    assert auth_module.enforce_account_rate_limit(1, "t", 5, cost=3) == 1
    assert auth_module.enforce_account_rate_limit(1, "t", 0) is None

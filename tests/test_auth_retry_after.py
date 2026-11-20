"""The auth limiter says how long to wait, like the per-account limiter does."""

import time
from collections import deque

import pytest
from fastapi.testclient import TestClient

from web_backend import auth as auth_module
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


def _login(client):
    return client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "x" * 10}
    )


def test_blocked_login_carries_retry_after(client):
    for _ in range(auth_module._RATE_LIMIT_MAX_ATTEMPTS):
        assert _login(client).status_code != 429

    blocked = _login(client)

    assert blocked.status_code == 429
    wait = int(blocked.headers["retry-after"])
    assert 1 <= wait <= auth_module._RATE_LIMIT_WINDOW_SECONDS + 1


def test_retry_after_shrinks_as_the_oldest_attempt_ages(client):
    window = auth_module._RATE_LIMIT_WINDOW_SECONDS
    now = time.time()
    # A full bucket whose oldest attempt is 100 s old: ~window - 100 s remain.
    key = "login:testclient"
    auth_module._auth_attempts[key] = deque(
        [now - 100] + [now - 10] * (auth_module._RATE_LIMIT_MAX_ATTEMPTS - 1)
    )

    blocked = _login(client)

    assert blocked.status_code == 429
    assert abs(int(blocked.headers["retry-after"]) - (window - 100)) <= 2

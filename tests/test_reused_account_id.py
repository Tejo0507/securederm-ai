"""A deleted account's leftovers must never reach the next account to get its id.

SQLite (without AUTOINCREMENT) gives a new row max(id) + 1, so deleting the
newest hospital hands its id to the next signup. Anything keyed by that id
alone (session tokens, audit events) would then carry over.
"""

import json
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from web_backend import auth as auth_module
from web_backend.main import app

TEST_PASSWORD = secrets.token_urlsafe(12)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


def _client():
    return TestClient(app, base_url="https://testserver")


def _sign_in(client, email):
    signup = client.post(
        "/api/auth/signup",
        json={"name": "Reuse Hospital", "email": email, "password": TEST_PASSWORD, "location": ""},
    )
    assert signup.status_code == 200, signup.text
    client.post("/api/auth/verify-email", json={"token": signup.json()["dev_verification_token"]})
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    return me.json()["id"], {auth_module.CSRF_HEADER_NAME: client.cookies.get(auth_module.CSRF_COOKIE_NAME)}


class TestSessionsIssuedBeforeTheAccountExisted:
    def test_a_token_older_than_the_account_is_rejected(self, monkeypatch):
        with _client() as client:
            hospital_id, _ = _sign_in(client, "reuse-old-token@example.com")

            # A token naming this id, issued an hour before the account was
            # created: exactly what a deleted predecessor's session looks like.
            real_time = auth_module.time.time
            monkeypatch.setattr(auth_module.time, "time", lambda: real_time() - 3600)
            stale = auth_module.create_token({"hospital_id": hospital_id, "email": "someone-else@example.com"})
            monkeypatch.setattr(auth_module.time, "time", real_time)

        with _client() as attacker:
            attacker.cookies.set(auth_module.SESSION_COOKIE_NAME, stale)
            resp = attacker.get("/api/auth/me")
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Session has been signed out"

    def test_the_accounts_own_sessions_still_work(self):
        with _client() as client:
            _sign_in(client, "reuse-own-token@example.com")
            assert client.get("/api/auth/me").status_code == 200

    def test_a_deleted_accounts_other_device_cannot_reach_the_next_signup(self):
        email = "reuse-deleted@example.com"
        with _client() as owner:
            _, headers = _sign_in(owner, email)
            with _client() as other_device:
                assert other_device.post(
                    "/api/auth/login", json={"email": email, "password": TEST_PASSWORD}
                ).status_code == 200

                deleted = owner.request(
                    "DELETE", "/api/auth/account", headers=headers, json={"password": TEST_PASSWORD}
                )
                assert deleted.status_code == 200

                with _client() as newcomer:
                    _sign_in(newcomer, "reuse-newcomer@example.com")

                # Whether or not the id was reused, the old device is out.
                assert other_device.get("/api/auth/me").status_code == 401

"""Tests for account self-service: profile editing and signing out everywhere."""

import secrets

import pytest
from fastapi.testclient import TestClient

from web_backend import auth as auth_module
from web_backend.main import app

# Generated per run: a fixture credential, never a literal in the repo.
TEST_PASSWORD = secrets.token_urlsafe(12)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _sign_in(client, email="account@example.com", name="Account Hospital", password=TEST_PASSWORD):
    signup = client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": password, "location": "Oldtown"},
    )
    client.post("/api/auth/verify-email", json={"token": signup.json()["dev_verification_token"]})
    return {auth_module.CSRF_HEADER_NAME: client.cookies.get(auth_module.CSRF_COOKIE_NAME)}


class TestProfileUpdate:
    def test_requires_auth_and_csrf(self, client):
        assert client.patch("/api/auth/me", json={"name": "X"}).status_code == 401
        _sign_in(client, "profile0@example.com")
        assert client.patch("/api/auth/me", json={"name": "X"}).status_code == 403

    def test_updates_name_and_location(self, client):
        headers = _sign_in(client, "profile1@example.com")
        resp = client.patch(
            "/api/auth/me", headers=headers, json={"name": "  St Mary  ", "location": "Newtown"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "St Mary"
        assert resp.json()["location"] == "Newtown"
        assert client.get("/api/auth/me").json()["name"] == "St Mary"

    def test_omitted_field_is_left_alone(self, client):
        headers = _sign_in(client, "profile2@example.com", name="Keep Me")
        resp = client.patch("/api/auth/me", headers=headers, json={"location": "Elsewhere"})
        assert resp.json()["name"] == "Keep Me"
        assert resp.json()["location"] == "Elsewhere"

    def test_location_can_be_cleared(self, client):
        headers = _sign_in(client, "profile3@example.com")
        resp = client.patch("/api/auth/me", headers=headers, json={"location": ""})
        assert resp.status_code == 200 and resp.json()["location"] == ""

    @pytest.mark.parametrize("body", [
        {},
        {"name": None, "location": None},
        {"name": "   "},
        {"name": "x" * 201},
        {"location": "y" * 201},
    ])
    def test_invalid_updates_are_rejected(self, client, body):
        headers = _sign_in(client, f"profile4-{abs(hash(str(body)))}@example.com")
        assert client.patch("/api/auth/me", headers=headers, json=body).status_code == 422

    def test_email_cannot_be_changed_through_the_profile(self, client):
        headers = _sign_in(client, "profile5@example.com")
        resp = client.patch(
            "/api/auth/me", headers=headers, json={"name": "Same", "email": "hijack@example.com"}
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "profile5@example.com"

    def test_change_is_audited_with_field_names_only(self, client):
        from web_backend.audit import read_events

        headers = _sign_in(client, "profile6@example.com")
        hospital_id = client.get("/api/auth/me").json()["id"]
        client.patch("/api/auth/me", headers=headers, json={"name": "Secret Name Inc"})
        event = read_events(hospital_id)[0]
        assert event["action"] == "profile_updated"
        assert event["fields"] == "name"
        assert "Secret Name Inc" not in str(event)

    def test_unchanged_values_write_no_audit_event(self, client):
        from web_backend.audit import read_events

        headers = _sign_in(client, "profile7@example.com", name="Same Name")
        hospital_id = client.get("/api/auth/me").json()["id"]
        before = len(read_events(hospital_id))
        client.patch("/api/auth/me", headers=headers, json={"name": "Same Name"})
        assert len(read_events(hospital_id)) == before

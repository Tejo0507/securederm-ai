"""Tests for account self-service: profile editing and signing out everywhere."""

import base64
import hashlib
import hmac
import json

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


class TestActivityFilters:
    def _event(self, hospital_id, action, ts):
        return {"ts": ts, "action": action, "hospital_id": hospital_id}

    @pytest.fixture
    def log(self, tmp_path, monkeypatch):
        """A throwaway audit log with a known, chronological history."""
        from web_backend import audit as audit_module

        path = tmp_path / "audit.log"
        events = [
            self._event(1, "login", "2026-01-01T10:00:00+00:00"),
            self._event(2, "login", "2026-01-02T10:00:00+00:00"),
            self._event(1, "dataset_upload", "2026-01-03T10:00:00+00:00"),
            self._event(1, "password_changed", "2026-01-04T10:00:00+00:00"),
            self._event(1, "login", "2026-01-05T10:00:00+00:00"),
        ]
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        monkeypatch.setattr(audit_module, "AUDIT_LOG_PATH", path)
        return audit_module

    def test_filter_by_action(self, log):
        events = log.read_events(1, actions={"login"})
        assert [e["ts"][:10] for e in events] == ["2026-01-05", "2026-01-01"]

    def test_multiple_actions(self, log):
        events = log.read_events(1, actions={"dataset_upload", "password_changed"})
        assert [e["action"] for e in events] == ["password_changed", "dataset_upload"]

    def test_since_is_inclusive_and_stops_at_older_events(self, log):
        from datetime import datetime, timezone

        events = log.read_events(1, since=datetime(2026, 1, 3, 10, tzinfo=timezone.utc))
        assert [e["ts"][:10] for e in events] == ["2026-01-05", "2026-01-04", "2026-01-03"]

    def test_naive_since_is_read_as_utc(self, log):
        from datetime import datetime

        assert len(log.read_events(1, since=datetime(2026, 1, 5))) == 1

    def test_filters_combine_with_limit(self, log):
        events = log.read_events(1, limit=1, actions={"login"})
        assert [e["ts"][:10] for e in events] == ["2026-01-05"]

    def test_endpoint_accepts_the_filters(self, client):
        headers = _sign_in(client, "activity1@example.com")
        client.patch("/api/auth/me", headers=headers, json={"name": "Renamed Hospital"})

        everything = client.get("/api/auth/activity").json()
        assert {"email_verified", "profile_updated"} <= {e["action"] for e in everything}

        only = client.get("/api/auth/activity?action=profile_updated").json()
        assert [e["action"] for e in only] == ["profile_updated"]

        recent = client.get("/api/auth/activity?since=2999-01-01T00:00:00Z").json()
        assert recent == []

    def test_endpoint_rejects_a_malformed_time(self, client):
        _sign_in(client, "activity2@example.com")
        assert client.get("/api/auth/activity?since=yesterday").status_code == 422


class TestSignOutEverywhere:
    def _second_device(self, email, password=TEST_PASSWORD):
        device = TestClient(app, base_url="https://testserver")
        assert device.post(
            "/api/auth/login", json={"email": email, "password": password}
        ).status_code == 200
        return device

    def test_requires_auth_and_csrf(self, client):
        assert client.post("/api/auth/logout-all").status_code == 401
        _sign_in(client, "everywhere0@example.com")
        assert client.post("/api/auth/logout-all").status_code == 403

    def test_ends_sessions_on_every_device(self, client):
        email = "everywhere1@example.com"
        headers = _sign_in(client, email)
        with self._second_device(email) as other:
            assert other.get("/api/auth/me").status_code == 200

            assert client.post("/api/auth/logout-all", headers=headers).status_code == 200

            assert client.get("/api/auth/me").status_code == 401
            resp = other.get("/api/auth/me")
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Session has been signed out"

    def test_signing_in_again_works_afterwards(self, client):
        email = "everywhere2@example.com"
        headers = _sign_in(client, email)
        client.post("/api/auth/logout-all", headers=headers)
        with self._second_device(email) as fresh:
            assert fresh.get("/api/auth/me").status_code == 200

    def test_other_accounts_are_unaffected(self, client):
        headers = _sign_in(client, "everywhere3a@example.com")
        with TestClient(app, base_url="https://testserver") as bystander:
            _sign_in(bystander, "everywhere3b@example.com")
            client.post("/api/auth/logout-all", headers=headers)
            assert bystander.get("/api/auth/me").status_code == 200

    def test_is_audited(self, client):
        from web_backend.audit import read_events

        headers = _sign_in(client, "everywhere4@example.com")
        hospital_id = client.get("/api/auth/me").json()["id"]
        client.post("/api/auth/logout-all", headers=headers)
        assert read_events(hospital_id)[0]["action"] == "sessions_revoked"

    def test_token_without_an_issue_time_is_rejected_after_the_cutoff(self, client):
        from web_backend.database import SessionLocal
        from web_backend.db_models import Hospital

        email = "everywhere5@example.com"
        headers = _sign_in(client, email)
        hospital_id = client.get("/api/auth/me").json()["id"]
        client.post("/api/auth/logout-all", headers=headers)

        legacy = auth_module.create_token({"hospital_id": hospital_id, "email": email})
        # Re-sign a payload that predates `iat`, the way an old token would look.
        header, body, _ = legacy.split(".")
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        data.pop("iat")
        new_body = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        sig = hmac.new(
            auth_module.SECRET_KEY.encode(), f"{header}.{new_body}".encode(), hashlib.sha256
        ).hexdigest()
        client.cookies.set(auth_module.SESSION_COOKIE_NAME, f"{header}.{new_body}.{sig}")
        assert client.get("/api/auth/me").status_code == 401

        db = SessionLocal()
        try:
            assert db.get(Hospital, hospital_id).sessions_valid_after is not None
        finally:
            db.close()


class TestSessionColumnMigration:
    def test_adds_the_column_to_a_database_that_predates_it(self, tmp_path, monkeypatch):
        import sqlite3

        from sqlalchemy import create_engine

        from web_backend import database

        db_file = tmp_path / "old.db"
        raw = sqlite3.connect(db_file)
        raw.execute(
            "CREATE TABLE hospitals (id INTEGER PRIMARY KEY, name VARCHAR(200), "
            "email VARCHAR(200), password_hash VARCHAR(500), location VARCHAR(200), "
            "created_at DATETIME, email_verified BOOLEAN NOT NULL DEFAULT 0, "
            "email_verification_token_hash VARCHAR(128), "
            "email_verification_expires_at DATETIME)"
        )
        raw.execute(
            "INSERT INTO hospitals (name, email, password_hash) VALUES ('Old', 'o@x.com', 'h')"
        )
        raw.commit()
        raw.close()

        engine = create_engine(f"sqlite:///{db_file}")
        monkeypatch.setattr(database, "engine", engine)
        database.run_migrations()

        with engine.connect() as conn:
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(hospitals)")}
            value = conn.exec_driver_sql("SELECT sessions_valid_after FROM hospitals").scalar()
        assert "sessions_valid_after" in columns
        assert value is None
        engine.dispose()


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

"""Tests for the date-range filters on the prediction history endpoints."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
from web_backend import auth as auth_module
from web_backend.database import SessionLocal
from web_backend.db_models import Prediction
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


def seed(hospital_id: int, when: datetime, label="Burns", confidence=0.9, unknown=False):
    db = SessionLocal()
    try:
        db.add(Prediction(
            hospital_id=hospital_id, model_id="m1", predicted_class=label,
            confidence=confidence, uncertainty=0.1, is_unknown=unknown, created_at=when,
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def account(client):
    """A signed-in hospital with one prediction on each of three days."""
    headers, _ = sign_in(client, "filters")
    hospital_id = client.get("/api/auth/me").json()["id"]
    seed(hospital_id, datetime(2026, 3, 1, 9), "Burns", 0.95)
    seed(hospital_id, datetime(2026, 3, 2, 9), "Cut", 0.40, unknown=True)
    seed(hospital_id, datetime(2026, 3, 3, 9), "Normal", 0.70)
    return headers, hospital_id


def _labels(client, query=""):
    body = client.get(f"/api/predictions?{query}").json()
    return [i["predicted_class"] for i in body["items"]]


class TestDateRange:
    def test_since_is_inclusive(self, client, account):
        assert _labels(client, "since=2026-03-02T09:00:00") == ["Normal", "Cut"]

    def test_until_is_exclusive(self, client, account):
        assert _labels(client, "until=2026-03-02T09:00:00") == ["Burns"]

    def test_a_window(self, client, account):
        assert _labels(client, "since=2026-03-02T00:00:00&until=2026-03-03T00:00:00") == ["Cut"]

    def test_date_only_values_are_accepted(self, client, account):
        assert _labels(client, "since=2026-03-03") == ["Normal"]

    def test_timezone_offsets_are_converted_to_utc(self, client, account):
        # 16:00+05:00 is 11:00 UTC, after the 09:00 UTC prediction: excluded.
        assert _labels(client, "since=2026-03-03T16:00:00%2B05:00") == []
        # 12:00+05:00 is 07:00 UTC, before it: included.
        assert _labels(client, "since=2026-03-03T12:00:00%2B05:00") == ["Normal"]

    def test_since_after_until_is_rejected(self, client, account):
        resp = client.get("/api/predictions?since=2026-03-03&until=2026-03-01")
        assert resp.status_code == 422
        assert "since" in resp.json()["detail"]

    def test_malformed_dates_are_rejected(self, client, account):
        assert client.get("/api/predictions?since=last-week").status_code == 422

    def test_total_reflects_the_filter_not_the_page(self, client, account):
        body = client.get("/api/predictions?since=2026-03-02&limit=1").json()
        assert body["total"] == 2 and len(body["items"]) == 1

    def test_combines_with_other_filters(self, client, account):
        assert _labels(client, "since=2026-03-01&unknown=true") == ["Cut"]

    def test_export_honours_the_range(self, client, account):
        text = client.get("/api/predictions/export?since=2026-03-03").text
        lines = text.strip().splitlines()
        assert len(lines) == 2 and ",Normal," in lines[1]

    def test_export_rejects_an_inverted_range(self, client, account):
        resp = client.get("/api/predictions/export?since=2026-03-03&until=2026-03-01")
        assert resp.status_code == 422

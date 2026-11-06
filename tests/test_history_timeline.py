"""Tests for GET /api/predictions/timeline."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
from tests.test_history_filters import seed
from web_backend import auth as auth_module
from web_backend.database import SessionLocal
from web_backend.main import app
from web_backend.prediction_history import daily_counts


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _at(day: date, hour=12) -> datetime:
    return datetime(day.year, day.month, day.day, hour)


def test_requires_auth(client):
    assert client.get("/api/predictions/timeline").status_code == 401


def test_empty_history_is_all_zeros_and_oldest_first(client):
    sign_in(client, "timeline-empty")
    body = client.get("/api/predictions/timeline?days=7").json()
    assert body["days"] == 7 and len(body["series"]) == 7
    dates = [p["date"] for p in body["series"]]
    assert dates == sorted(dates)
    assert dates[-1] == _today().isoformat()
    assert all(p["total"] == 0 and p["unknown"] == 0 for p in body["series"])


def test_counts_land_on_the_right_days(client):
    sign_in(client, "timeline-counts")
    hospital_id = client.get("/api/auth/me").json()["id"]
    today = _today()
    seed(hospital_id, _at(today), unknown=False)
    seed(hospital_id, _at(today, 3), unknown=True)
    seed(hospital_id, _at(today - timedelta(days=2)), unknown=True)

    payload = client.get("/api/predictions/timeline?days=5").json()
    series = {p["date"]: p for p in payload["series"]}
    assert series[today.isoformat()] == {"date": today.isoformat(), "total": 2, "unknown": 1}
    two_days_ago = (today - timedelta(days=2)).isoformat()
    assert series[two_days_ago]["total"] == 1 and series[two_days_ago]["unknown"] == 1
    assert series[(today - timedelta(days=1)).isoformat()]["total"] == 0


def test_older_than_the_window_is_excluded(client):
    sign_in(client, "timeline-window")
    hospital_id = client.get("/api/auth/me").json()["id"]
    seed(hospital_id, _at(_today() - timedelta(days=10)))
    series = client.get("/api/predictions/timeline?days=3").json()["series"]
    assert sum(p["total"] for p in series) == 0


def test_default_is_thirty_days(client):
    sign_in(client, "timeline-default")
    assert len(client.get("/api/predictions/timeline").json()["series"]) == 30


@pytest.mark.parametrize("days", [0, -1, 366, "x"])
def test_days_must_be_between_1_and_365(client, days):
    sign_in(client, "timeline-bounds")
    assert client.get(f"/api/predictions/timeline?days={days}").status_code == 422


def test_only_own_predictions_are_counted(client):
    sign_in(client, "timeline-own")
    mine = client.get("/api/auth/me").json()["id"]
    seed(mine, _at(_today()))
    with TestClient(app, base_url="https://testserver") as other:
        sign_in(other, "timeline-other")
        series = other.get("/api/predictions/timeline?days=2").json()["series"]
        assert sum(p["total"] for p in series) == 0


def test_does_not_shadow_the_single_entry_route(client):
    sign_in(client, "timeline-route")
    assert client.get("/api/predictions/timeline").status_code == 200
    assert client.get("/api/predictions/424242").status_code == 404


def test_daily_counts_with_a_fixed_today():
    db = SessionLocal()
    try:
        series = daily_counts(db, hospital_id=-1, days=3, today=date(2026, 1, 3))
    finally:
        db.close()
    assert [p["date"] for p in series] == ["2026-01-01", "2026-01-02", "2026-01-03"]

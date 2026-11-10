"""Rows written by the database's own timestamp default have no fractional
seconds, while the ORM writes six digits. Day boundaries must treat both the
same: `since` is inclusive and `until` exclusive."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.support import sign_in
from web_backend import auth as auth_module
from web_backend.database import engine
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


def _insert_raw(hospital_id: int, *stamps: str) -> None:
    """Insert with explicit text stamps, exactly as the server default would write them."""
    with engine.begin() as conn:
        for stamp in stamps:
            conn.execute(
                text(
                    "INSERT INTO predictions (hospital_id, model_id, predicted_class, confidence,"
                    " uncertainty, is_unknown, created_at) VALUES (:h, 'm', 'Burns', .9, .1, 0, :t)"
                ),
                {"h": hospital_id, "t": stamp},
            )


def _stamps(client, query):
    items = client.get(f"/api/predictions?{query}").json()["items"]
    return sorted(i["created_at"] for i in items)


@pytest.fixture
def account(client):
    sign_in(client, "boundary")
    hospital_id = client.get("/api/auth/me").json()["id"]
    _insert_raw(
        hospital_id,
        "2026-03-01 00:00:00",          # exactly midnight, no fraction (server default)
        "2026-03-01 12:00:00",
        "2026-03-02 00:00:00",          # exactly the next midnight
        "2026-03-02 00:00:00.000000",   # same instant, written the ORM way
        "2026-03-01 23:59:59.999999",
    )
    return hospital_id


def test_since_includes_a_row_stamped_exactly_on_the_bound(client, account):
    assert "2026-03-01T00:00:00" in _stamps(client, "since=2026-03-01")


def test_until_excludes_a_row_stamped_exactly_on_the_bound(client, account):
    stamps = _stamps(client, "until=2026-03-02")
    assert not [s for s in stamps if s.startswith("2026-03-02")]
    assert len(stamps) == 3     # 03-01 00:00:00, 03-01 12:00:00, 03-01 23:59:59.999999


def test_a_whole_day_is_exactly_that_day(client, account):
    assert _stamps(client, "since=2026-03-01&until=2026-03-02") == [
        "2026-03-01T00:00:00", "2026-03-01T12:00:00", "2026-03-01T23:59:59.999999",
    ]


def test_the_next_day_starts_at_its_midnight(client, account):
    stamps = _stamps(client, "since=2026-03-02&until=2026-03-03")
    assert len(stamps) == 2 and all(s.startswith("2026-03-02T00:00:00") for s in stamps)


def test_a_bound_with_a_fraction_still_compares_correctly(client, account):
    stamps = _stamps(client, "since=2026-03-01T23:59:59.5")
    assert "2026-03-01T23:59:59.999999" in stamps
    assert "2026-03-01T12:00:00" not in stamps


def test_a_second_precision_bound_between_stored_formats(client, account):
    # 12:00:00 (no fraction) sits exactly on the bound: included by since, not by until.
    assert "2026-03-01T12:00:00" in _stamps(client, "since=2026-03-01T12:00:00")
    assert "2026-03-01T12:00:00" not in _stamps(client, "until=2026-03-01T12:00:00")


def test_export_uses_the_same_boundaries(client, account):
    lines = client.get(
        "/api/predictions/export?since=2026-03-01&until=2026-03-02"
    ).text.strip().splitlines()
    assert len(lines) == 1 + 3


class TestTimelineBoundaries:
    def test_a_midnight_row_counts_on_its_own_day(self, client):
        sign_in(client, "timeline-boundary")
        hospital_id = client.get("/api/auth/me").json()["id"]
        today = datetime.now(timezone.utc).date()
        first = today - timedelta(days=4)
        _insert_raw(
            hospital_id,
            f"{first.isoformat()} 00:00:00",                        # first instant of the window
            f"{today.isoformat()} 23:59:59",                        # last second of today
            f"{(today + timedelta(days=1)).isoformat()} 00:00:00",  # tomorrow: outside
        )

        series = {
            p["date"]: p["total"]
            for p in client.get("/api/predictions/timeline?days=5").json()["series"]
        }
        assert series[first.isoformat()] == 1
        assert series[today.isoformat()] == 1
        assert sum(series.values()) == 2

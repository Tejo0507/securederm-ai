"""Numbers that SQLite cannot hold must be a 422, never a 500."""

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
from web_backend import auth as auth_module
from web_backend.limits import MAX_DB_INT, MAX_OFFSET
from web_backend.main import app

HUGE = 10 ** 25


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    # raise_server_exceptions=False so a regression shows up as a 500, not a test crash
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def signed_in(client):
    headers, _ = sign_in(client, "bounds")
    return headers


class TestIdsBeyondTheDatabaseRange:
    @pytest.mark.parametrize("path", [
        f"/api/predictions/{HUGE}",
        f"/api/predictions/{MAX_DB_INT + 1}",
        f"/api/models/{HUGE}",
        f"/api/models/-{HUGE}",
        "/api/predictions/0",
        "/api/predictions/-1",
        "/api/models/0",
    ])
    def test_get_is_rejected_cleanly(self, client, signed_in, path):
        assert client.get(path).status_code == 422

    def test_delete_is_rejected_cleanly(self, client, signed_in):
        resp = client.delete(f"/api/predictions/{HUGE}", headers=signed_in)
        assert resp.status_code == 422

    def test_the_largest_valid_id_is_just_not_found(self, client, signed_in):
        assert client.get(f"/api/predictions/{MAX_DB_INT}").status_code == 404
        assert client.get(f"/api/models/{MAX_DB_INT}").status_code == 404


class TestDatesBeyondTheRepresentableRange:
    @pytest.mark.parametrize("query", [
        "since=0001-01-01T00:00:00%2B14:00",    # before year 1 once converted to UTC
        "until=0001-01-01T00:00:00%2B14:00",
        "since=9999-12-31T23:59:59-14:00",      # after year 9999 once converted to UTC
        "until=9999-12-31T23:59:59-14:00",
    ])
    @pytest.mark.parametrize("path", ["/api/predictions", "/api/predictions/export"])
    def test_unrepresentable_instants_are_a_422(self, client, signed_in, path, query):
        resp = client.get(f"{path}?{query}")
        assert resp.status_code == 422
        assert "date out of range" in resp.json()["detail"]

    @pytest.mark.parametrize("query", [
        "since=0001-01-01", "until=9999-12-31", "since=0001-01-01T00:00:00Z",
        "until=9999-12-31T23:59:59Z",
    ])
    def test_the_extremes_themselves_are_fine(self, client, signed_in, query):
        assert client.get(f"/api/predictions?{query}").status_code == 200

    def test_the_conversion_helper_reports_the_problem_as_a_value_error(self):
        from datetime import datetime, timedelta, timezone

        from web_backend.prediction_history import to_naive_utc

        with pytest.raises(ValueError):
            to_naive_utc(datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14))))


class TestOffsetsBeyondTheDatabaseRange:
    @pytest.mark.parametrize("path", [
        "/api/predictions",
        "/api/hospitals",
        "/api/models",
        "/api/datasets",
        "/api/datasets/images",
    ])
    def test_a_huge_offset_is_rejected_cleanly(self, client, signed_in, path):
        assert client.get(f"{path}?offset={HUGE}").status_code == 422
        assert client.get(f"{path}?offset={MAX_OFFSET + 1}").status_code == 422

    @pytest.mark.parametrize("path", [
        "/api/predictions", "/api/hospitals", "/api/models", "/api/datasets",
    ])
    def test_the_largest_allowed_offset_just_returns_nothing(self, client, signed_in, path):
        resp = client.get(f"{path}?offset={MAX_OFFSET}")
        assert resp.status_code == 200

    def test_a_huge_limit_is_still_a_422(self, client, signed_in):
        assert client.get(f"/api/predictions?limit={HUGE}").status_code == 422

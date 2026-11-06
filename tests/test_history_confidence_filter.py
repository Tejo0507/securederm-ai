"""Tests for the min_confidence / max_confidence history filters."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
from tests.test_history_filters import seed
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


@pytest.fixture
def account(client):
    sign_in(client, "confidence")
    hospital_id = client.get("/api/auth/me").json()["id"]
    for day, (label, confidence) in enumerate(
        [("Burns", 0.95), ("Cut", 0.40), ("Normal", 0.70), ("Bruises", 0.55)], start=1
    ):
        seed(hospital_id, datetime(2026, 4, day, 9), label, confidence)
    return hospital_id


def _labels(client, query):
    return [i["predicted_class"] for i in client.get(f"/api/predictions?{query}").json()["items"]]


def test_min_confidence_is_inclusive(client, account):
    assert _labels(client, "min_confidence=0.7") == ["Normal", "Burns"]


def test_max_confidence_is_inclusive(client, account):
    assert _labels(client, "max_confidence=0.55") == ["Bruises", "Cut"]


def test_band(client, account):
    assert _labels(client, "min_confidence=0.5&max_confidence=0.8") == ["Bruises", "Normal"]


def test_finds_low_confidence_cases_for_review(client, account):
    body = client.get("/api/predictions?max_confidence=0.5").json()
    assert body["total"] == 1 and body["items"][0]["predicted_class"] == "Cut"


def test_combines_with_date_range(client, account):
    assert _labels(client, "min_confidence=0.5&since=2026-04-03") == ["Bruises", "Normal"]


@pytest.mark.parametrize("query", [
    "min_confidence=-0.1", "min_confidence=1.1", "max_confidence=2", "min_confidence=high",
])
def test_out_of_range_values_are_rejected(client, account, query):
    assert client.get(f"/api/predictions?{query}").status_code == 422


def test_inverted_band_is_rejected(client, account):
    resp = client.get("/api/predictions?min_confidence=0.9&max_confidence=0.1")
    assert resp.status_code == 422 and "min_confidence" in resp.json()["detail"]


def test_export_honours_the_band(client, account):
    lines = client.get("/api/predictions/export?min_confidence=0.9").text.strip().splitlines()
    assert len(lines) == 2 and ",Burns," in lines[1]

"""Tests for GET /api/network/stats."""

import pytest
from fastapi.testclient import TestClient

from tests.support import png_bytes, sign_in
from web_backend import auth as auth_module
from web_backend.database import SessionLocal
from web_backend.db_models import FederatedRound
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


def _stats(client):
    return client.get("/api/network/stats").json()


def test_requires_auth(client):
    assert client.get("/api/network/stats").status_code == 401


def test_shape(client):
    sign_in(client, "stats-shape")
    assert set(_stats(client)) == {
        "hospitals", "models", "images", "rounds_recorded",
        "latest_round", "latest_avg_loss", "best_avg_loss",
    }


def test_hospital_count_grows_with_signups(client):
    sign_in(client, "stats-count")
    before = _stats(client)["hospitals"]
    with TestClient(app, base_url="https://testserver") as other:
        sign_in(other, "stats-count-2")
    assert _stats(client)["hospitals"] == before + 1


def test_marketplace_models_are_counted(client):
    sign_in(client, "stats-models")
    assert _stats(client)["models"] == len(client.get("/api/models?limit=100").json())


def test_images_are_summed_across_the_network(client):
    headers, _ = sign_in(client, "stats-images")
    before = _stats(client)["images"]
    client.post("/api/datasets/upload", headers=headers, files=[
        ("files", ("a.png", png_bytes((1, 1, 1)), "image/png")),
        ("files", ("b.png", png_bytes((2, 2, 2)), "image/png")),
    ])
    assert _stats(client)["images"] == before + 2


def test_round_figures_follow_the_recorded_rounds(client):
    sign_in(client, "stats-rounds")
    db = SessionLocal()
    try:
        db.query(FederatedRound).delete()
        db.add_all([
            FederatedRound(round_number=1, participating_hospitals="A, B", avg_loss=1.5),
            FederatedRound(round_number=2, participating_hospitals="A, B", avg_loss=0.9),
            FederatedRound(round_number=3, participating_hospitals="A, B", avg_loss=1.1),
        ])
        db.commit()
    finally:
        db.close()

    stats = _stats(client)
    assert stats["rounds_recorded"] == 3
    assert stats["latest_round"] == 3
    assert stats["latest_avg_loss"] == pytest.approx(1.1)
    assert stats["best_avg_loss"] == pytest.approx(0.9)


def test_no_rounds_yet_reports_nulls(client):
    sign_in(client, "stats-norounds")
    db = SessionLocal()
    try:
        db.query(FederatedRound).delete()
        db.commit()
    finally:
        db.close()
    stats = _stats(client)
    assert stats["rounds_recorded"] == 0
    assert stats["latest_round"] is None
    assert stats["latest_avg_loss"] is None and stats["best_avg_loss"] is None


def test_exposes_no_per_hospital_detail(client):
    sign_in(client, "stats-private", name="Very Identifiable Hospital")
    text = client.get("/api/network/stats").text
    assert "Very Identifiable" not in text and "@" not in text

"""Tests for GET /api/models/{id}."""

import pytest
from fastapi.testclient import TestClient

from web_backend.main import app


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def test_returns_the_same_shape_as_the_listing(client):
    listed = client.get("/api/models").json()
    assert listed, "the marketplace is seeded on startup"
    first = listed[0]
    detail = client.get(f"/api/models/{first['id']}")
    assert detail.status_code == 200
    assert detail.json() == first


def test_every_listed_model_is_reachable(client):
    for model in client.get("/api/models").json():
        assert client.get(f"/api/models/{model['id']}").json()["model_name"] == model["model_name"]


def test_unknown_model_is_404(client):
    resp = client.get("/api/models/987654")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Model not found."


def test_non_numeric_id_is_rejected(client):
    assert client.get("/api/models/latest").status_code == 422


def test_marketplace_is_public_like_the_listing(client):
    # No session cookie at all.
    first = client.get("/api/models").json()[0]
    assert client.get(f"/api/models/{first['id']}").status_code == 200

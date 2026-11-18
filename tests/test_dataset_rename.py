"""Renaming a hospital renames the dataset that was titled after it."""

import pytest
from fastapi.testclient import TestClient

from tests.support import png_bytes, sign_in
from web_backend import auth as auth_module
from web_backend.database import SessionLocal
from web_backend.db_models import Dataset
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


def _upload_one(client, headers):
    client.post(
        "/api/datasets/upload", headers=headers,
        files=[("files", ("a.png", png_bytes((9, 9, 9)), "image/png"))],
    )


def _dataset_names(client):
    return [d["name"] for d in client.get("/api/datasets").json()]


def test_the_default_dataset_name_follows_a_rename(client):
    headers, _ = sign_in(client, "rename-ds", name="Old Name")
    _upload_one(client, headers)
    assert _dataset_names(client) == ["Old Name Dataset"]

    resp = client.patch("/api/auth/me", headers=headers, json={"name": "New Name"})

    assert resp.status_code == 200
    assert _dataset_names(client) == ["New Name Dataset"]


def test_a_dataset_with_its_own_title_is_left_alone(client):
    headers, _ = sign_in(client, "rename-custom", name="Before")
    _upload_one(client, headers)
    hospital_id = client.get("/api/auth/me").json()["id"]
    db = SessionLocal()
    try:
        db.query(Dataset).filter(Dataset.hospital_id == hospital_id).update(
            {Dataset.name: "Dermatology 2026"}
        )
        db.commit()
    finally:
        db.close()

    client.patch("/api/auth/me", headers=headers, json={"name": "After"})

    assert _dataset_names(client) == ["Dermatology 2026"]


def test_a_location_change_does_not_touch_the_dataset(client):
    headers, _ = sign_in(client, "rename-loc", name="Steady")
    _upload_one(client, headers)

    client.patch("/api/auth/me", headers=headers, json={"location": "Elsewhere"})

    assert _dataset_names(client) == ["Steady Dataset"]


def test_new_datasets_use_the_current_name(client):
    headers, _ = sign_in(client, "rename-first", name="First")
    client.patch("/api/auth/me", headers=headers, json={"name": "Second"})

    _upload_one(client, headers)

    assert _dataset_names(client) == ["Second Dataset"]

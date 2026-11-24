"""An upload in which nothing is accepted must not create a dataset."""

import pytest
from fastapi.testclient import TestClient

from tests.support import png_bytes, sign_in
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


def _upload(client, headers, *files):
    return client.post(
        "/api/datasets/upload",
        headers=headers,
        files=[("files", (name, content, "image/png")) for name, content in files],
    )


def test_rejected_files_leave_no_empty_dataset(client):
    headers, _ = sign_in(client, "rejected")

    resp = _upload(client, headers, ("notes.png", b"not an image"), ("empty.png", b""))

    assert resp.status_code == 200
    assert resp.json()["uploaded"] == 0
    assert resp.json()["total_images"] == 0
    assert client.get("/api/datasets").json() == []


def test_the_dataset_appears_with_the_first_accepted_image(client):
    headers, _ = sign_in(client, "first-accepted")
    _upload(client, headers, ("notes.png", b"not an image"))

    resp = _upload(client, headers, ("bad.png", b"nope"), ("wound.png", png_bytes()))

    assert resp.json()["uploaded"] == 1
    assert [d["image_count"] for d in client.get("/api/datasets").json()] == [1]

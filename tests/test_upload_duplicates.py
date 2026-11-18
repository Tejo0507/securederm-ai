"""An upload says how many of its images were already stored.

Images are stored under a hash of their pixels, so sending the same photo twice
keeps one file. The response used to count both sends as uploads, which made
"Uploaded 6 images (3 total)" read like a bug.
"""

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


def _upload(client, headers, *pngs):
    files = [("files", (f"p{i}.png", data, "image/png")) for i, data in enumerate(pngs)]
    return client.post("/api/datasets/upload", headers=headers, files=files).json()


def test_new_images_report_no_duplicates(client):
    headers, _ = sign_in(client, "dup-new")

    body = _upload(client, headers, png_bytes((10, 20, 30)), png_bytes((30, 20, 10)))

    assert body["uploaded"] == 2
    assert body["duplicates"] == 0
    assert body["total_images"] == 2


def test_sending_the_same_image_again_is_a_duplicate(client):
    headers, _ = sign_in(client, "dup-again")
    same = png_bytes((5, 6, 7))
    _upload(client, headers, same)

    body = _upload(client, headers, same, png_bytes((8, 9, 10)))

    assert body["uploaded"] == 2
    assert body["duplicates"] == 1
    assert body["total_images"] == 2


def test_the_same_image_twice_in_one_request_counts_once(client):
    headers, _ = sign_in(client, "dup-batch")
    same = png_bytes((77, 77, 77))

    body = _upload(client, headers, same, same)

    assert body["duplicates"] == 1
    assert body["total_images"] == 1


def test_a_duplicate_does_not_move_the_original_upload_time(client):
    headers, _ = sign_in(client, "dup-time")
    same = png_bytes((1, 2, 3))
    _upload(client, headers, same)
    first = client.get("/api/datasets/images").json()["items"][0]

    _upload(client, headers, same)
    second = client.get("/api/datasets/images").json()["items"][0]

    assert second == first

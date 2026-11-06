"""Tests for listing and deleting individual stored dataset images."""

import os

import pytest
from fastapi.testclient import TestClient

from tests.support import png_bytes, sign_in
from web_backend import auth as auth_module
from web_backend.main import app
from web_backend.routers import hospital_router


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _upload(client, headers, *colors):
    parts = [("files", (f"p{i}.png", png_bytes(c), "image/png")) for i, c in enumerate(colors)]
    return client.post("/api/datasets/upload", headers=headers, files=parts)


class TestListImages:
    def test_requires_auth(self, client):
        assert client.get("/api/datasets/images").status_code == 401

    def test_empty(self, client):
        sign_in(client, "images-empty")
        assert client.get("/api/datasets/images").json() == {"total": 0, "items": []}

    def test_lists_name_size_and_time_only(self, client):
        headers, _ = sign_in(client, "images-list")
        _upload(client, headers, (1, 2, 3), (4, 5, 6))
        body = client.get("/api/datasets/images").json()
        assert body["total"] == 2
        item = body["items"][0]
        assert set(item) == {"name", "size_bytes", "uploaded_at"}
        assert item["size_bytes"] > 0 and item["uploaded_at"].endswith("+00:00")
        # Names are derived from pixel data: nothing the uploader typed.
        assert "p0" not in item["name"] and "p1" not in item["name"]

    def test_newest_first_and_paged(self, client):
        headers, _ = sign_in(client, "images-paged")
        _upload(client, headers, (1, 1, 1), (2, 2, 2), (3, 3, 3))
        hospital_id = client.get("/api/auth/me").json()["id"]
        folder = hospital_router.UPLOAD_DIR / str(hospital_id)
        for age, path in enumerate(sorted(folder.iterdir())):
            os.utime(path, (1_700_000_000 + age * 100,) * 2)

        everything = client.get("/api/datasets/images").json()["items"]
        times = [i["uploaded_at"] for i in everything]
        assert times == sorted(times, reverse=True)

        page = client.get("/api/datasets/images?limit=1&offset=2").json()
        assert page["total"] == 3
        assert [i["name"] for i in page["items"]] == [everything[2]["name"]]

    def test_page_bounds(self, client):
        sign_in(client, "images-bounds")
        assert client.get("/api/datasets/images?limit=0").status_code == 422
        assert client.get("/api/datasets/images?limit=101").status_code == 422
        assert client.get("/api/datasets/images?offset=-1").status_code == 422

    def test_only_own_images(self, client):
        headers, _ = sign_in(client, "images-own")
        _upload(client, headers, (9, 9, 9))
        with TestClient(app, base_url="https://testserver") as other:
            sign_in(other, "images-other")
            assert other.get("/api/datasets/images").json()["total"] == 0

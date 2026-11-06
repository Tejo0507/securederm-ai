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


class TestDeleteImage:
    def _names(self, client):
        return [i["name"] for i in client.get("/api/datasets/images").json()["items"]]

    def test_requires_auth_and_csrf(self, client):
        assert client.delete(f"/api/datasets/images/{'a' * 32}.png").status_code == 401
        sign_in(client, "del-csrf")
        assert client.delete(f"/api/datasets/images/{'a' * 32}.png").status_code == 403

    def test_deletes_one_image_and_updates_the_count(self, client):
        headers, _ = sign_in(client, "del-one")
        _upload(client, headers, (1, 2, 3), (4, 5, 6))
        first, second = self._names(client)

        resp = client.delete(f"/api/datasets/images/{first}", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {"deleted": first, "total_images": 1}
        assert self._names(client) == [second]
        assert client.get("/api/datasets").json()[0]["image_count"] == 1
        assert client.get("/api/datasets/summary").json()["images"] == 1

    def test_unknown_image_is_404(self, client):
        headers, _ = sign_in(client, "del-missing")
        resp = client.delete(f"/api/datasets/images/{'b' * 32}.png", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.parametrize("name", [
        "..%2F..%2Fsecret.png", "not-a-hash.png", f"{'a' * 32}.exe", f"{'A' * 32}.png",
        f"{'a' * 31}.png", f"{'a' * 32}.png.png",
    ])
    def test_malformed_or_traversal_names_never_reach_the_disk(self, client, name):
        headers, _ = sign_in(client, "del-bad")
        resp = client.delete(f"/api/datasets/images/{name}", headers=headers)
        assert resp.status_code in (404, 422)

    def test_cannot_delete_another_hospitals_image(self, client):
        headers, _ = sign_in(client, "del-owner")
        _upload(client, headers, (7, 7, 7))
        (name,) = self._names(client)

        with TestClient(app, base_url="https://testserver") as other:
            other_headers, _ = sign_in(other, "del-intruder")
            resp = other.delete(f"/api/datasets/images/{name}", headers=other_headers)
            assert resp.status_code == 404
        assert self._names(client) == [name]

    def test_is_audited(self, client):
        from web_backend.audit import read_events

        headers, _ = sign_in(client, "del-audit")
        hospital_id = client.get("/api/auth/me").json()["id"]
        _upload(client, headers, (8, 8, 8))
        (name,) = self._names(client)
        client.delete(f"/api/datasets/images/{name}", headers=headers)
        event = read_events(hospital_id)[0]
        assert event["action"] == "dataset_image_erased" and event["images"] == 1
        assert name not in str(event)


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

"""Image processing during an upload must not run on the event loop."""

import asyncio

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


def test_images_are_sanitised_in_a_worker_thread(client, monkeypatch):
    on_loop = []
    real_sanitize = hospital_router.sanitize_image

    def recording(content):
        try:
            asyncio.get_running_loop()
            on_loop.append(True)
        except RuntimeError:   # no loop in this thread
            on_loop.append(False)
        return real_sanitize(content)

    monkeypatch.setattr(hospital_router, "sanitize_image", recording)
    headers, _ = sign_in(client, "offloop")

    resp = client.post(
        "/api/datasets/upload",
        headers=headers,
        files=[("files", ("wound.png", png_bytes(), "image/png"))],
    )

    assert resp.json()["uploaded"] == 1
    assert on_loop == [False]

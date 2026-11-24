"""A cut-off image is a bad request, not a server error.

JPEG, BMP and TIFF files that stop part-way still have a valid header, so they
pass the first check and only fail once the pixels are decoded.
"""

import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.support import sign_in, use_predictor
from web_backend import auth as auth_module
from web_backend.image_validation import is_genuine_image
from web_backend.main import app

pytestmark = pytest.mark.security


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _truncated(fmt: str) -> bytes:
    # Noise barely compresses, so half the file is well past the header.
    noise = Image.frombytes("RGB", (128, 128), os.urandom(128 * 128 * 3))
    buf = io.BytesIO()
    noise.save(buf, format=fmt)
    data = buf.getvalue()
    return data[: len(data) // 2]


@pytest.mark.parametrize("fmt", ["JPEG", "BMP", "TIFF"])
def test_truncated_image_is_rejected_with_400(client, monkeypatch, fmt):
    use_predictor(monkeypatch)
    headers, _ = sign_in(client, "truncated")
    content = _truncated(fmt)
    assert is_genuine_image(content), "the point of this test: the header looks fine"

    resp = client.post(
        "/api/predict", headers=headers, files={"file": ("cut", content, "image/jpeg")}
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Could not decode image."
    assert client.get("/api/predictions").json()["total"] == 0

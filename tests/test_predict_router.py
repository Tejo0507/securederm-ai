"""Tests for POST /api/predict.

The real model checkpoint (checkpoints/global_model.pt) is gitignored and
may not exist in every environment this suite runs in (a fresh clone, or
CI), so these tests monkeypatch model.inference.get_predictor rather than
depending on it — what's under test here is the endpoint's auth/CSRF/
input-validation/error-handling behavior, not the model itself (that's
covered by tests/test_model.py).
"""

import io
import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="securederm_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DB_DIR, 'test.db')}"
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from web_backend.main import app  # noqa: E402
from web_backend import auth as auth_module  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _signed_in_headers(client, email="predictor@example.com") -> dict:
    signup = client.post(
        "/api/auth/signup",
        json={
            "name": "Predict Test Hospital",
            "email": email,
            "password": "supersecret1",
            "location": "X",
        },
    )
    token = signup.json()["dev_verification_token"]
    client.post("/api/auth/verify-email", json={"token": token})
    csrf = client.cookies.get(auth_module.CSRF_COOKIE_NAME)
    return {auth_module.CSRF_HEADER_NAME: csrf} if csrf else {}


def _real_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(150, 70, 60)).save(buf, format="PNG")
    return buf.getvalue()


class _FakePredictionResult:
    predicted_class = "Burns"
    confidence = 0.91
    is_unknown = False
    message = "Predicted 'Burns' with 91% confidence."
    class_probabilities = {"Burns": 0.91, "Abrasions": 0.09}


class _FakePredictor:
    def predict(self, image):
        return _FakePredictionResult()


class TestPredictAuth:
    def test_predict_requires_auth(self, client):
        resp = client.post(
            "/api/predict",
            files={"file": ("wound.png", _real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 401

    def test_predict_requires_csrf_header(self, client):
        _signed_in_headers(client)  # establishes session cookie, headers unused here
        resp = client.post(
            "/api/predict",
            files={"file": ("wound.png", _real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 403


class TestPredictInputValidation:
    def test_predict_rejects_non_image(self, client, monkeypatch):
        monkeypatch.setattr("model.inference.get_predictor", lambda: _FakePredictor())
        headers = _signed_in_headers(client, email="badinput@example.com")
        resp = client.post(
            "/api/predict",
            headers=headers,
            files={"file": ("notreally.png", b"not an image at all", "image/png")},
        )
        assert resp.status_code == 400

    def test_predict_rejects_oversized_file(self, client, monkeypatch):
        monkeypatch.setattr("model.inference.get_predictor", lambda: _FakePredictor())
        headers = _signed_in_headers(client, email="oversized@example.com")
        from web_backend.image_validation import MAX_FILE_SIZE_BYTES

        oversized = b"\x00" * (MAX_FILE_SIZE_BYTES + 1)
        resp = client.post(
            "/api/predict",
            headers=headers,
            files={"file": ("huge.png", oversized, "image/png")},
        )
        assert resp.status_code == 413


class TestPredictSuccess:
    def test_predict_returns_prediction_for_genuine_image(self, client, monkeypatch):
        monkeypatch.setattr("model.inference.get_predictor", lambda: _FakePredictor())
        headers = _signed_in_headers(client, email="success@example.com")
        resp = client.post(
            "/api/predict",
            headers=headers,
            files={"file": ("wound.png", _real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["predicted_class"] == "Burns"
        assert data["is_unknown"] is False
        assert "class_probabilities" in data

    def test_predict_returns_503_when_no_model_available(self, client, monkeypatch):
        def _raise_missing():
            raise FileNotFoundError("no checkpoint")

        monkeypatch.setattr("model.inference.get_predictor", _raise_missing)
        headers = _signed_in_headers(client, email="nomodel@example.com")
        resp = client.post(
            "/api/predict",
            headers=headers,
            files={"file": ("wound.png", _real_png_bytes(), "image/png")},
        )
        assert resp.status_code == 503

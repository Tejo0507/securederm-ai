"""Helpers shared by newer web-backend tests.

All tests in a run share one database, so every account gets a unique e-mail
address; passwords are generated per run instead of being literals.
"""

import io
import secrets
import uuid

from PIL import Image

from web_backend import auth as auth_module

PASSWORD = secrets.token_urlsafe(12)


def unique_email(label: str = "user") -> str:
    return f"{label}-{uuid.uuid4().hex[:10]}@example.com"


def sign_in(client, label: str = "user", name: str = "Test Hospital", location: str = "Testville"):
    """Create and verify an account, leaving `client` signed in.

    Returns (csrf_headers, email).
    """
    email = unique_email(label)
    signup = client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": PASSWORD, "location": location},
    )
    client.post("/api/auth/verify-email", json={"token": signup.json()["dev_verification_token"]})
    headers = {auth_module.CSRF_HEADER_NAME: client.cookies.get(auth_module.CSRF_COOKIE_NAME)}
    return headers, email


def png_bytes(color=(150, 70, 60), size=32) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=color).save(buf, format="PNG")
    return buf.getvalue()


class FakeResult:
    def __init__(self, label="Burns", confidence=0.91, unknown=False, model_id="abc123def456"):
        self.predicted_class = label
        self.confidence = confidence
        self.is_unknown = unknown
        self.message = "ok"
        self.class_probabilities = {label: confidence}
        self.top_predictions = [{"label": label, "probability": confidence}]
        self.uncertainty = 0.2
        self.model_id = model_id


class FakePredictor:
    """Answers with the queued results in order, then repeats the last one."""

    def __init__(self, *results):
        self.queue = list(results) or [FakeResult()]

    def _next(self):
        return self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]

    def predict(self, image):
        return self._next()

    def predict_batch(self, images):
        return [self._next() for _ in images]


def use_predictor(monkeypatch, *results) -> FakePredictor:
    predictor = FakePredictor(*results)
    monkeypatch.setattr("model.inference.get_predictor", lambda: predictor)
    return predictor

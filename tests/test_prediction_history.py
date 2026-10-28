"""Tests for the per-hospital prediction history.

The model itself is faked (see test_predict_router.py for why); what is
under test is what the web layer records, exposes and erases.
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from web_backend import auth as auth_module
from web_backend.database import SessionLocal
from web_backend.db_models import Hospital, Prediction
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


class _Result:
    def __init__(self, label="Burns", confidence=0.91, unknown=False, model_id="abc123def456"):
        self.predicted_class = label
        self.confidence = confidence
        self.is_unknown = unknown
        self.message = "ok"
        self.class_probabilities = {label: confidence}
        self.top_predictions = [{"label": label, "probability": confidence}]
        self.uncertainty = 0.2
        self.model_id = model_id


class _Predictor:
    """Answers with the queued results in order, then repeats the last one."""

    def __init__(self, *results):
        self.queue = list(results) or [_Result()]

    def _next(self):
        return self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]

    def predict(self, image):
        return self._next()

    def predict_batch(self, images):
        return [self._next() for _ in images]


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(150, 70, 60)).save(buf, format="PNG")
    return buf.getvalue()


def _sign_in(client, email="history@example.com") -> dict:
    signup = client.post(
        "/api/auth/signup",
        json={"name": "History Hospital", "email": email,
              "password": "supersecret1", "location": "X"},
    )
    client.post("/api/auth/verify-email", json={"token": signup.json()["dev_verification_token"]})
    return {auth_module.CSRF_HEADER_NAME: client.cookies.get(auth_module.CSRF_COOKIE_NAME)}


def _use_predictor(monkeypatch, *results):
    predictor = _Predictor(*results)
    monkeypatch.setattr("model.inference.get_predictor", lambda: predictor)
    return predictor


def _predict(client, headers):
    return client.post(
        "/api/predict", headers=headers, files={"file": ("w.png", _png(), "image/png")}
    )


def _rows(email):
    db = SessionLocal()
    try:
        hospital = db.query(Hospital).filter(Hospital.email == email).one()
        return db.query(Prediction).filter(Prediction.hospital_id == hospital.id).all()
    finally:
        db.close()


class TestRecording:
    def test_successful_prediction_is_recorded(self, client, monkeypatch):
        _use_predictor(monkeypatch, _Result("Burns", 0.91))
        headers = _sign_in(client, "rec1@example.com")
        assert _predict(client, headers).status_code == 200

        rows = _rows("rec1@example.com")
        assert len(rows) == 1
        assert rows[0].predicted_class == "Burns"
        assert rows[0].confidence == pytest.approx(0.91)
        assert rows[0].model_id == "abc123def456"
        assert rows[0].is_unknown is False

    def test_rejected_upload_is_not_recorded(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        headers = _sign_in(client, "rec2@example.com")
        resp = client.post(
            "/api/predict", headers=headers,
            files={"file": ("x.png", b"not an image", "image/png")},
        )
        assert resp.status_code == 400
        assert _rows("rec2@example.com") == []

    def test_history_failure_does_not_fail_the_prediction(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        headers = _sign_in(client, "rec3@example.com")

        def _boom(*args, **kwargs):
            raise RuntimeError("disk full")

        monkeypatch.setattr("web_backend.prediction_history.Prediction", _boom)
        assert _predict(client, headers).status_code == 200

    def test_no_image_data_in_the_table(self):
        columns = {c.name for c in Prediction.__table__.columns}
        assert columns.isdisjoint({"image", "filename", "content", "probabilities"})


class TestListing:
    def test_requires_auth(self, client):
        assert client.get("/api/predictions").status_code == 401

    def test_lists_newest_first_with_total(self, client, monkeypatch):
        _use_predictor(monkeypatch, _Result("Burns"), _Result("Cut"), _Result("Normal"))
        headers = _sign_in(client, "list1@example.com")
        for _ in range(3):
            _predict(client, headers)

        body = client.get("/api/predictions").json()
        assert body["total"] == 3
        assert [i["predicted_class"] for i in body["items"]] == ["Normal", "Cut", "Burns"]
        assert set(body["items"][0]) == {
            "id", "created_at", "model_id", "predicted_class",
            "confidence", "uncertainty", "is_unknown",
        }

    def test_paginates(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        headers = _sign_in(client, "list2@example.com")
        for _ in range(5):
            _predict(client, headers)

        page = client.get("/api/predictions?limit=2&offset=4").json()
        assert page["total"] == 5
        assert len(page["items"]) == 1
        assert client.get("/api/predictions?limit=0").status_code == 422
        assert client.get("/api/predictions?limit=101").status_code == 422

    def test_filters_by_label_and_unknown(self, client, monkeypatch):
        _use_predictor(
            monkeypatch,
            _Result("Burns"), _Result("Cut", 0.3, unknown=True), _Result("Burns"),
        )
        headers = _sign_in(client, "list3@example.com")
        for _ in range(3):
            _predict(client, headers)

        assert client.get("/api/predictions?label=Burns").json()["total"] == 2
        unknown = client.get("/api/predictions?unknown=true").json()
        assert unknown["total"] == 1 and unknown["items"][0]["predicted_class"] == "Cut"
        assert client.get("/api/predictions?unknown=false").json()["total"] == 2

    def test_only_own_predictions_are_visible(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        headers = _sign_in(client, "list4a@example.com")
        _predict(client, headers)

        with TestClient(app, base_url="https://testserver") as other:
            _sign_in(other, "list4b@example.com")
            assert other.get("/api/predictions").json() == {"total": 0, "items": []}

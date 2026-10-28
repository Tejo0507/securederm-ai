"""Tests for the per-hospital prediction history.

The model itself is faked (see test_predict_router.py for why); what is
under test is what the web layer records, exposes and erases.
"""

import io

import secrets

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from web_backend import auth as auth_module
from web_backend.database import SessionLocal
from web_backend.db_models import Hospital, Prediction
from web_backend.main import app

# Generated per run: a fixture credential, never a literal in the repo.
TEST_PASSWORD = secrets.token_urlsafe(12)


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
              "password": TEST_PASSWORD, "location": "X"},
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


class TestExport:
    def test_requires_auth(self, client):
        assert client.get("/api/predictions/export").status_code == 401

    def test_exports_csv_with_header_and_rows(self, client, monkeypatch):
        _use_predictor(monkeypatch, _Result("Burns", 0.9), _Result("Cut", 0.4, unknown=True))
        headers = _sign_in(client, "csv1@example.com")
        for _ in range(2):
            _predict(client, headers)

        resp = client.get("/api/predictions/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        lines = resp.text.strip().splitlines()
        assert lines[0] == "id,created_at,model_id,predicted_class,confidence,uncertainty,is_unknown"
        assert len(lines) == 3
        assert ",Cut,0.4," in lines[1] and lines[1].endswith(",True")

    def test_export_respects_filters(self, client, monkeypatch):
        _use_predictor(monkeypatch, _Result("Burns"), _Result("Cut"))
        headers = _sign_in(client, "csv2@example.com")
        for _ in range(2):
            _predict(client, headers)
        lines = client.get("/api/predictions/export?label=Burns").text.strip().splitlines()
        assert len(lines) == 2 and ",Burns," in lines[1]

    def test_formula_cells_are_neutralised(self):
        from web_backend.prediction_history import _csv_safe, history_to_csv

        assert _csv_safe("=HYPERLINK(\"x\")").startswith("'=")
        assert _csv_safe("@SUM(A1)").startswith("'@")
        assert _csv_safe("Burns") == "Burns"
        assert _csv_safe(0.5) == "0.5"
        assert history_to_csv([]).count("\n") == 1   # header only


class TestPredictRateLimit:
    def test_limit_is_per_account_and_reports_retry_after(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        monkeypatch.setattr("web_backend.routers.predict_router.PREDICT_RATE_LIMIT_PER_MINUTE", 2)
        headers = _sign_in(client, "rate1@example.com")

        assert _predict(client, headers).status_code == 200
        assert _predict(client, headers).status_code == 200
        blocked = _predict(client, headers)
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) >= 1

        # A different account is unaffected by the first one's usage.
        with TestClient(app, base_url="https://testserver") as other:
            other_headers = _sign_in(other, "rate2@example.com")
            assert _predict(other, other_headers).status_code == 200

    def test_rejected_requests_are_not_recorded(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        monkeypatch.setattr("web_backend.routers.predict_router.PREDICT_RATE_LIMIT_PER_MINUTE", 1)
        headers = _sign_in(client, "rate3@example.com")
        _predict(client, headers)
        _predict(client, headers)
        assert len(_rows("rate3@example.com")) == 1

    def test_zero_disables_the_limit(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        monkeypatch.setattr("web_backend.routers.predict_router.PREDICT_RATE_LIMIT_PER_MINUTE", 0)
        headers = _sign_in(client, "rate4@example.com")
        assert all(_predict(client, headers).status_code == 200 for _ in range(5))


class TestErasure:
    def test_requires_auth_and_csrf(self, client):
        assert client.delete("/api/predictions").status_code == 401
        _sign_in(client, "erase0@example.com")
        assert client.delete("/api/predictions").status_code == 403

    def test_erases_only_own_history(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        headers = _sign_in(client, "erase1@example.com")
        for _ in range(3):
            _predict(client, headers)

        with TestClient(app, base_url="https://testserver") as other:
            other_headers = _sign_in(other, "history-erase-other@example.com")
            _predict(other, other_headers)

            resp = client.delete("/api/predictions", headers=headers)
            assert resp.status_code == 200
            assert resp.json() == {"deleted_predictions": 3}
            assert client.get("/api/predictions").json()["total"] == 0
            assert other.get("/api/predictions").json()["total"] == 1

    def test_erasure_is_audited(self, client, monkeypatch):
        from web_backend.audit import read_events

        _use_predictor(monkeypatch)
        headers = _sign_in(client, "erase3@example.com")
        _predict(client, headers)
        hospital_id = client.get("/api/auth/me").json()["id"]
        client.delete("/api/predictions", headers=headers)
        assert read_events(hospital_id)[0]["action"] == "history_erased"

    def test_deleting_the_account_removes_history(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        headers = _sign_in(client, "erase4@example.com")
        _predict(client, headers)
        assert len(_rows("erase4@example.com")) == 1
        hospital_id = client.get("/api/auth/me").json()["id"]

        resp = client.request(
            "DELETE", "/api/auth/account", headers=headers, json={"password": TEST_PASSWORD}
        )
        assert resp.status_code == 200
        db = SessionLocal()
        try:
            assert db.query(Prediction).filter(Prediction.hospital_id == hospital_id).count() == 0
        finally:
            db.close()


class TestSummary:
    def test_requires_auth(self, client):
        assert client.get("/api/predictions/summary").status_code == 401

    def test_empty_history(self, client):
        _sign_in(client, "sum1@example.com")
        body = client.get("/api/predictions/summary").json()
        assert body["total"] == 0
        assert body["unknown_rate"] == 0.0
        assert body["average_confidence"] is None
        assert body["by_class"] == {} and body["by_model"] == []
        assert body["first_at"] is None and body["last_at"] is None

    def test_aggregates(self, client, monkeypatch):
        _use_predictor(
            monkeypatch,
            _Result("Burns", 0.9, model_id="m1"),
            _Result("Burns", 0.7, model_id="m1"),
            _Result("Cut", 0.2, unknown=True, model_id="m2"),
            _Result("Normal", 0.8, model_id="m2"),
        )
        headers = _sign_in(client, "sum2@example.com")
        for _ in range(4):
            _predict(client, headers)

        body = client.get("/api/predictions/summary").json()
        assert body["total"] == 4
        assert body["unknown"] == 1
        assert body["unknown_rate"] == 0.25
        assert body["average_confidence"] == pytest.approx(0.65)
        assert body["by_class"] == {"Burns": 2, "Cut": 1, "Normal": 1}
        assert body["by_model"] == [
            {"model_id": "m1", "count": 2}, {"model_id": "m2", "count": 2},
        ]
        assert body["first_at"] and body["last_at"]

    def test_summary_is_scoped_to_the_account(self, client, monkeypatch):
        _use_predictor(monkeypatch)
        headers = _sign_in(client, "sum3a@example.com")
        _predict(client, headers)

        with TestClient(app, base_url="https://testserver") as other:
            _sign_in(other, "sum3b@example.com")
            assert other.get("/api/predictions/summary").json()["total"] == 0

"""Tests for the deployed-model description (model.inference.model_info and
GET /api/model/info). No real checkpoint is needed: model_info() only hashes
the file, so a few arbitrary bytes stand in for one."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from config.settings import CLASS_LABELS
from model import inference
from web_backend import auth as auth_module
from web_backend.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def checkpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(inference, "CHECKPOINTS_DIR", tmp_path)
    inference._id_cache.clear()
    yield tmp_path
    inference._id_cache.clear()


class TestModelInfo:
    def test_unavailable_without_a_checkpoint(self, checkpoints):
        info = inference.model_info()
        assert info["available"] is False
        assert "model_id" not in info
        assert info["classes"] == [CLASS_LABELS[i] for i in sorted(CLASS_LABELS)]

    def test_describes_the_checkpoint(self, checkpoints):
        payload = b"not really weights"
        (checkpoints / "global_model.pt").write_bytes(payload)

        info = inference.model_info()
        assert info["available"] is True
        assert info["model_id"] == hashlib.sha256(payload).hexdigest()[:12]
        assert info["size_bytes"] == len(payload)
        assert info["updated_at"].endswith("+00:00")
        assert info["unknown_threshold"] == inference.OOD_CONFIDENCE_THRESHOLD

    def test_fingerprint_tracks_the_file(self, checkpoints):
        path = checkpoints / "global_model.pt"
        path.write_bytes(b"first")
        first = inference.model_info()["model_id"]
        path.write_bytes(b"second, longer")
        assert inference.model_info()["model_id"] != first

    def test_hash_is_cached_while_the_file_is_unchanged(self, checkpoints, monkeypatch):
        (checkpoints / "global_model.pt").write_bytes(b"weights")
        inference.model_info()

        def _fail(path):
            raise AssertionError("rehashed an unchanged checkpoint")

        monkeypatch.setattr(inference, "_checkpoint_id", _fail)
        assert inference.model_info()["available"] is True

    def test_matches_the_id_stamped_on_predictions(self, checkpoints):
        path = checkpoints / "global_model.pt"
        path.write_bytes(b"abc")
        assert inference.model_info()["model_id"] == inference._checkpoint_id(path)


class TestModelInfoEndpoint:
    def test_requires_auth(self):
        with TestClient(app, base_url="https://testserver") as client:
            assert client.get("/api/model/info").status_code == 401

    def test_returns_info_to_a_signed_in_hospital(self, checkpoints):
        (checkpoints / "global_model.pt").write_bytes(b"weights")
        with TestClient(app, base_url="https://testserver") as client:
            signup = client.post(
                "/api/auth/signup",
                json={"name": "Info Hospital", "email": "info@example.com",
                      "password": "supersecret1", "location": "X"},
            )
            client.post(
                "/api/auth/verify-email", json={"token": signup.json()["dev_verification_token"]}
            )
            resp = client.get("/api/model/info")
        assert resp.status_code == 200
        assert resp.json()["available"] is True
        assert len(resp.json()["model_id"]) == 12

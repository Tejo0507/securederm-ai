"""A checkpoint that exists but cannot be loaded makes diagnosis unavailable."""

import pytest
from fastapi.testclient import TestClient

import model.inference as inference
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


@pytest.fixture
def corrupt_checkpoint(tmp_path, monkeypatch):
    (tmp_path / "global_model.pt").write_bytes(b"half a download")
    monkeypatch.setattr(inference, "CHECKPOINTS_DIR", tmp_path)
    monkeypatch.setattr(inference, "_predictor", None)
    monkeypatch.setattr(inference, "_predictor_stamp", None)


@pytest.mark.parametrize("path, field", [("/api/predict", "file"),
                                         ("/api/predict/batch", "files")])
def test_corrupt_checkpoint_answers_503(client, corrupt_checkpoint, path, field):
    headers, _ = sign_in(client, "corrupt-model")

    resp = client.post(
        path, headers=headers, files=[(field, ("wound.png", png_bytes(), "image/png"))]
    )

    assert resp.status_code == 503
    assert "could not be loaded" in resp.json()["detail"]

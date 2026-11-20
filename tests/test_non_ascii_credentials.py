"""Credentials with non-ASCII characters are rejected, never a server error.

``secrets.compare_digest`` raises TypeError for non-ASCII ``str`` input, and
header values and JSON strings are chosen by the caller. A wrong credential
must always be a 4xx answer.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from aggregator import server as server_module
from aggregator.server import app
from config.secure_compare import constant_time_equals

pytestmark = pytest.mark.security

# Header values travel as latin-1 bytes; this decodes to "tökén" server-side.
NON_ASCII_HEADER = "tökén".encode("latin-1")


class TestConstantTimeEquals:
    def test_equal_values_match(self):
        assert constant_time_equals("abc", "abc")

    def test_different_values_do_not_match(self):
        assert not constant_time_equals("abc", "abd")
        assert not constant_time_equals("abc", "abcd")

    def test_non_ascii_does_not_raise(self):
        assert constant_time_equals("tökén", "tökén")
        assert not constant_time_equals("token", "tökén")

    def test_lone_surrogates_do_not_raise(self):
        assert not constant_time_equals("token", "\ud800")

    def test_missing_values_never_match(self):
        assert not constant_time_equals(None, "")
        assert not constant_time_equals("", None)
        assert not constant_time_equals(None, None)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server_module, "AGGREGATOR_ADMIN_TOKEN", "operator-secret")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _enroll(client):
    hospital_id = f"ascii_{uuid.uuid4().hex[:8]}"
    token = client.post(
        "/node/register", json={"hospital_id": hospital_id, "dataset_size": 25}
    ).json()["node_token"]
    return hospital_id, token


@pytest.mark.parametrize("path", ["/nodes", "/model/latest", "/round/metrics"])
def test_non_ascii_node_token_is_refused_on_protected_reads(client, path):
    _enroll(client)  # at least one registered node, so every token is compared
    response = client.get(path, headers={"X-Node-Token": NON_ASCII_HEADER})
    assert response.status_code == 403


def test_status_gives_a_non_ascii_token_only_the_liveness_reply(client):
    _enroll(client)
    response = client.get("/status", headers={"X-Node-Token": NON_ASCII_HEADER})
    assert response.status_code == 200
    assert response.json() == {"status": "running"}


def test_non_ascii_token_is_refused_on_update(client):
    hospital_id, _ = _enroll(client)
    response = client.post(
        "/training/update",
        headers={"X-Node-Token": NON_ASCII_HEADER},
        json={
            "hospital_id": hospital_id,
            "model_weights_b64": "AAAA",
            "num_samples": 5,
            "training_loss": 0.5,
        },
    )
    assert response.status_code == 403


def test_re_registering_with_a_non_ascii_token_is_a_conflict(client):
    hospital_id, _ = _enroll(client)
    response = client.post(
        "/node/register",
        headers={"X-Node-Token": NON_ASCII_HEADER},
        json={"hospital_id": hospital_id, "dataset_size": 25},
    )
    assert response.status_code == 409


def test_non_ascii_registration_key_is_forbidden(client, monkeypatch):
    monkeypatch.setattr(server_module, "AGGREGATOR_REGISTRATION_KEY", "enrol-key")
    response = client.post(
        "/node/register",
        headers={"X-Registration-Key": NON_ASCII_HEADER},
        json={"hospital_id": f"ascii_{uuid.uuid4().hex[:8]}", "dataset_size": 25},
    )
    assert response.status_code == 403

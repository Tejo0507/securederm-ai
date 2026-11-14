"""422 responses carry one sentence a person can act on."""

import secrets

import pytest
from fastapi.testclient import TestClient

from web_backend import auth as auth_module
from web_backend.main import app, validation_message

PASSWORD = secrets.token_urlsafe(12)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _signup(client, **overrides):
    body = {"name": "Msg Hospital", "email": "msg@example.com", "password": PASSWORD}
    return client.post("/api/auth/signup", json={**body, **overrides})


class TestSignupMessages:
    def test_reserved_domain_reads_as_plain_advice(self, client):
        resp = _signup(client, email="someone@example.test")
        assert resp.status_code == 422
        assert resp.json()["detail"] == "Enter a valid email address."

    def test_malformed_email(self, client):
        resp = _signup(client, email="not-an-email")
        assert resp.json()["detail"] == "Enter a valid email address."

    def test_custom_validator_message_has_no_prefix(self, client):
        resp = _signup(client, email="common@example.com", password="password123")
        assert resp.status_code == 422
        assert resp.json()["detail"].startswith("This password is too common.")

    def test_other_body_fields_get_a_readable_label(self, client):
        resp = _signup(client, email="short@example.com", password="short")
        assert resp.status_code == 422
        assert resp.json()["detail"].startswith("Password: ")


class TestValidationMessageUnit:
    def test_query_parameters_keep_their_exact_name(self):
        msg = "Input should be less than or equal to 1"
        error = {"loc": ("query", "min_confidence"), "msg": msg}
        assert validation_message(error) == f"min_confidence: {msg}"

    def test_snake_case_body_fields_become_words(self):
        msg = "String should have at least 12 characters"
        error = {"loc": ("body", "new_password"), "msg": msg}
        expected = "New password: string should have at least 12 characters"
        assert validation_message(error) == expected

    def test_missing_location(self):
        assert validation_message({"loc": (), "msg": "Field required"}) == "input: Field required"

"""Hospital names and locations are stored the way a person would read them."""

import pytest
from fastapi.testclient import TestClient

from tests.support import PASSWORD, unique_email
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


def _signup(client, **overrides):
    body = {
        "name": "Riverside Clinic", "email": unique_email("names"),
        "password": PASSWORD, "location": "Leeds",
    }
    body.update(overrides)
    return client.post("/api/auth/signup", json=body)


def _verify(client, signup):
    token = signup.json()["dev_verification_token"]
    return client.post("/api/auth/verify-email", json={"token": token})


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t\n"])
def test_a_blank_name_is_refused_with_a_sentence(client, blank):
    resp = _signup(client, name=blank)

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Hospital name cannot be empty."


def test_names_and_locations_lose_their_padding(client):
    signup = _signup(client, name="  St Mary's  ", location="  Leeds ")
    assert signup.status_code == 200, signup.text

    hospital = _verify(client, signup).json()

    assert hospital["name"] == "St Mary's"
    assert hospital["location"] == "Leeds"


def test_a_location_of_spaces_is_stored_as_empty(client):
    signup = _signup(client, location="    ")
    assert signup.status_code == 200, signup.text

    assert _verify(client, signup).json()["location"] == ""


def test_an_overlong_name_is_still_refused(client):
    assert _signup(client, name="x" * 201).status_code == 422

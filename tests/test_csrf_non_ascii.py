"""A malformed CSRF header is a 403, not a server error.

The header value is chosen by the caller, and secrets.compare_digest raises
TypeError when handed non-ASCII text.
"""

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
from web_backend import auth as auth_module
from web_backend.main import app

pytestmark = pytest.mark.security


@pytest.fixture
def client():
    auth_module._auth_attempts.clear()
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as c:
        yield c
    auth_module._auth_attempts.clear()


def test_non_ascii_csrf_header_is_refused(client):
    sign_in(client)
    response = client.post(
        "/api/training/stop",
        headers={auth_module.CSRF_HEADER_NAME: "tökén".encode("latin-1")},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF check failed."


def test_matching_csrf_header_is_still_accepted(client):
    headers, _ = sign_in(client)
    response = client.post("/api/training/stop", headers=headers)
    assert response.status_code == 200

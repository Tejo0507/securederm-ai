"""The rounds list shows the most recent work, not the highest round numbers.

Every training run records rounds 1 to 5. Sorting by round number put round 5
of every old run ahead of round 4 of the newest one, so after a few runs the
Network tab stopped showing anything new.
"""

import pytest
from fastapi.testclient import TestClient

from tests.support import sign_in
from web_backend import auth as auth_module
from web_backend.database import SessionLocal
from web_backend.db_models import FederatedRound
from web_backend.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        sign_in(c, "round-order")
        yield c


def _record_run(losses):
    """Append one run's rounds the way the simulation does: 1, 2, 3, ..."""
    db = SessionLocal()
    try:
        for number, loss in enumerate(losses, start=1):
            db.add(FederatedRound(
                round_number=number, participating_hospitals="A, B", avg_loss=loss,
            ))
        db.commit()
    finally:
        db.close()


def test_the_latest_run_comes_first_even_after_many_older_ones(client):
    for _ in range(5):
        _record_run([9.1, 9.2, 9.3, 9.4, 9.5])    # older runs, all ending in round 5
    _record_run([1.1, 1.2, 1.3, 1.4, 1.5])        # the run that just finished

    rounds = client.get("/api/federated/rounds").json()

    assert [r["avg_loss"] for r in rounds[:5]] == [1.5, 1.4, 1.3, 1.2, 1.1]
    assert [r["round_number"] for r in rounds[:5]] == [5, 4, 3, 2, 1]


def test_metrics_are_bounded_and_end_with_the_latest_round(client):
    for _ in range(25):
        _record_run([3.0, 3.0, 3.0, 3.0, 3.0])
    _record_run([0.5, 0.6, 0.7, 0.8, 0.9])

    metrics = client.get("/api/training/metrics").json()["metrics"]

    assert len(metrics) == 100
    assert [m["avg_loss"] for m in metrics[-5:]] == [0.5, 0.6, 0.7, 0.8, 0.9]
    assert [m["round"] for m in metrics[-5:]] == [1, 2, 3, 4, 5]
    assert all(m["nodes"] == 2 for m in metrics)


def test_the_list_is_still_capped_at_twenty(client):
    for _ in range(6):
        _record_run([2.0, 2.0, 2.0, 2.0, 2.0])

    assert len(client.get("/api/federated/rounds").json()) == 20

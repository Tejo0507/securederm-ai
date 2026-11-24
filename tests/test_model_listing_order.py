"""The marketplace lists models in a defined order, even when timestamps tie."""

from fastapi.testclient import TestClient

from web_backend.database import SessionLocal
from web_backend.db_models import MLModel
from web_backend.main import app


def test_models_with_the_same_timestamp_are_listed_newest_id_first():
    with TestClient(app, base_url="https://testserver") as client:   # seeds the samples
        db = SessionLocal()
        try:
            expected = [
                m.id for m in sorted(
                    db.query(MLModel).all(), key=lambda m: (m.created_at, m.id), reverse=True
                )
            ]
        finally:
            db.close()

        listed = [m["id"] for m in client.get("/api/models?limit=100").json()]
        paged = [
            client.get(f"/api/models?limit=1&offset={offset}").json()[0]["id"]
            for offset in range(len(expected))
        ]

    assert listed == expected
    assert paged == expected

"""Read access to a hospital's own prediction history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from web_backend.auth import get_current_hospital
from web_backend.database import get_db
from web_backend.db_models import Hospital
from web_backend.prediction_history import history_query, serialize_prediction

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

router = APIRouter()


@router.get("/predictions")
async def list_predictions(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
    label: str | None = Query(default=None, max_length=64),
    unknown: bool | None = None,
    model_id: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """This hospital's past predictions, newest first, with the total match
    count so a client can page through them."""
    query = history_query(db, hospital.id, label, unknown, model_id)
    return {
        "total": query.count(),
        "items": [serialize_prediction(r) for r in query.offset(offset).limit(limit).all()],
    }

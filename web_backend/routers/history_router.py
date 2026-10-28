"""Read access to a hospital's own prediction history."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from web_backend.audit import audit
from web_backend.auth import get_current_hospital, verify_csrf
from web_backend.database import get_db
from web_backend.db_models import Hospital, Prediction
from web_backend.prediction_history import (
    MAX_EXPORT_ROWS,
    history_query,
    history_to_csv,
    serialize_prediction,
    summarize_history,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

router = APIRouter()


@router.get("/predictions/summary")
async def predictions_summary(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """Totals, unknown rate, average confidence and per-class / per-model
    counts across this hospital's whole history."""
    return summarize_history(db, hospital.id)


@router.get("/predictions/export")
async def export_predictions(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
    label: str | None = Query(default=None, max_length=64),
    unknown: bool | None = None,
    model_id: str | None = Query(default=None, max_length=32),
):
    """Download the (optionally filtered) history as a CSV file, newest first,
    capped at MAX_EXPORT_ROWS rows."""
    rows = history_query(db, hospital.id, label, unknown, model_id).limit(MAX_EXPORT_ROWS).all()
    audit("history_exported", hospital.id, rows=len(rows))
    return Response(
        content=history_to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="prediction-history.csv"'},
    )


@router.delete("/predictions")
async def erase_predictions(
    request: Request,
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """Erase this hospital's entire prediction history."""
    verify_csrf(request)
    removed = db.query(Prediction).filter(Prediction.hospital_id == hospital.id).delete()
    db.commit()
    audit("history_erased", hospital.id, rows=removed)
    return {"deleted_predictions": removed}


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

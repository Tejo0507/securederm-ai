"""Read access to a hospital's own prediction history."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from web_backend.audit import audit
from web_backend.limits import MAX_DB_INT, MAX_OFFSET
from web_backend.auth import get_current_hospital, verify_csrf
from web_backend.database import get_db
from web_backend.db_models import Hospital, Prediction
from web_backend.prediction_history import (
    MAX_EXPORT_ROWS,
    daily_counts,
    history_query,
    history_to_csv,
    serialize_prediction,
    summarize_history,
    to_naive_utc,
)

PredictionId = Annotated[int, Path(ge=1, le=MAX_DB_INT)]

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

router = APIRouter()


def history_filters(
    label: str | None = Query(default=None, max_length=64),
    unknown: bool | None = None,
    model_id: str | None = Query(default=None, max_length=32),
    since: datetime | None = Query(
        default=None, description="Only predictions at or after this ISO-8601 time (UTC if no zone)"
    ),
    until: datetime | None = Query(
        default=None, description="Only predictions before this ISO-8601 time (UTC if no zone)"
    ),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    max_confidence: float | None = Query(default=None, ge=0, le=1),
) -> dict:
    """The filters shared by the list and export endpoints."""
    bounds = {}
    for name, value in (("since", since), ("until", until)):
        try:
            bounds[name] = to_naive_utc(value) if value is not None else None
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{name}: date out of range")
    since, until = bounds["since"], bounds["until"]
    if since is not None and until is not None and since > until:
        raise HTTPException(status_code=422, detail="since: must not be after until")
    if (
        min_confidence is not None and max_confidence is not None
        and min_confidence > max_confidence
    ):
        raise HTTPException(
            status_code=422, detail="min_confidence: must not be above max_confidence"
        )
    return {
        "label": label, "unknown": unknown, "model_id": model_id, "since": since, "until": until,
        "min_confidence": min_confidence, "max_confidence": max_confidence,
    }


@router.get("/predictions/summary")
async def predictions_summary(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """Totals, unknown rate, average confidence and per-class / per-model
    counts across this hospital's whole history."""
    return summarize_history(db, hospital.id)


@router.get("/predictions/timeline")
async def predictions_timeline(
    days: int = Query(default=30, ge=1, le=365),
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """Predictions per UTC day for the last `days` days (default 30), oldest
    first, with empty days included as zeros."""
    return {"days": days, "series": daily_counts(db, hospital.id, days)}


@router.get("/predictions/export")
async def export_predictions(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
    filters: dict = Depends(history_filters),
):
    """Download the (optionally filtered) history as a CSV file, newest first,
    capped at MAX_EXPORT_ROWS rows."""
    rows = history_query(db, hospital.id, **filters).limit(MAX_EXPORT_ROWS).all()
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
    filters: dict = Depends(history_filters),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0, le=MAX_OFFSET),
):
    """This hospital's past predictions, newest first, with the total match
    count so a client can page through them."""
    query = history_query(db, hospital.id, **filters)
    return {
        "total": query.count(),
        "items": [serialize_prediction(r) for r in query.offset(offset).limit(limit).all()],
    }


def _own_prediction(db: Session, hospital_id: int, prediction_id: int) -> Prediction:
    # The same 404 whether the row is missing or belongs to someone else, so
    # ids cannot be probed to learn how much another hospital has predicted.
    row = (
        db.query(Prediction)
        .filter(Prediction.id == prediction_id, Prediction.hospital_id == hospital_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Prediction not found.")
    return row


@router.get("/predictions/{prediction_id}")
async def get_prediction(
    prediction_id: PredictionId,
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """One of this hospital's predictions."""
    return serialize_prediction(_own_prediction(db, hospital.id, prediction_id))


@router.delete("/predictions/{prediction_id}")
async def delete_prediction(
    prediction_id: PredictionId,
    request: Request,
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """Erase a single prediction from this hospital's history."""
    verify_csrf(request)
    db.delete(_own_prediction(db, hospital.id, prediction_id))
    db.commit()
    audit("history_entry_erased", hospital.id)
    return {"deleted_predictions": 1}

"""Per-hospital prediction history.

A hospital can review how the model has been used on its account — how many
diagnoses, which classes, how often the model said "unknown" — without the
platform ever keeping a patient image or a diagnosis tied to a person.
"""

import csv
import io
import logging

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from web_backend.db_models import Prediction

logger = logging.getLogger("web_backend.history")


def history_query(
    db: Session,
    hospital_id: int,
    label: str | None = None,
    unknown: bool | None = None,
    model_id: str | None = None,
):
    """The hospital's own predictions, newest first, narrowed by the filters."""
    query = db.query(Prediction).filter(Prediction.hospital_id == hospital_id)
    if label:
        query = query.filter(Prediction.predicted_class == label)
    if unknown is not None:
        query = query.filter(Prediction.is_unknown == unknown)
    if model_id:
        query = query.filter(Prediction.model_id == model_id)
    return query.order_by(Prediction.created_at.desc(), Prediction.id.desc())


def serialize_prediction(row: Prediction) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "model_id": row.model_id,
        "predicted_class": row.predicted_class,
        "confidence": row.confidence,
        "uncertainty": row.uncertainty,
        "is_unknown": row.is_unknown,
    }


def summarize_history(db: Session, hospital_id: int) -> dict:
    """Aggregate usage figures for one hospital's predictions."""
    own = Prediction.hospital_id == hospital_id
    total, unknown, avg_confidence, first, last = db.query(
        func.count(Prediction.id),
        func.coalesce(func.sum(case((Prediction.is_unknown, 1), else_=0)), 0),
        func.avg(Prediction.confidence),
        func.min(Prediction.created_at),
        func.max(Prediction.created_at),
    ).filter(own).one()

    by_class = dict(
        db.query(Prediction.predicted_class, func.count(Prediction.id))
        .filter(own)
        .group_by(Prediction.predicted_class)
        .order_by(func.count(Prediction.id).desc(), Prediction.predicted_class)
        .all()
    )
    by_model = [
        {"model_id": model_id, "count": count}
        for model_id, count in db.query(Prediction.model_id, func.count(Prediction.id))
        .filter(own)
        .group_by(Prediction.model_id)
        .order_by(func.count(Prediction.id).desc(), Prediction.model_id)
        .all()
    ]
    return {
        "total": total,
        "unknown": unknown,
        "unknown_rate": round(unknown / total, 4) if total else 0.0,
        "average_confidence": round(avg_confidence, 4) if avg_confidence is not None else None,
        "first_at": first.isoformat() if first else None,
        "last_at": last.isoformat() if last else None,
        "by_class": by_class,
        "by_model": by_model,
    }


CSV_COLUMNS = ["id", "created_at", "model_id", "predicted_class", "confidence",
               "uncertainty", "is_unknown"]
MAX_EXPORT_ROWS = 50_000


def _csv_safe(value) -> str:
    """Neutralise spreadsheet formula injection: a cell starting with = + - @
    is executed by Excel/Sheets when the file is opened."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def history_to_csv(rows) -> str:
    """Render prediction rows (newest first) as CSV text with a header row."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        record = serialize_prediction(row)
        writer.writerow([_csv_safe(record[column]) for column in CSV_COLUMNS])
    return out.getvalue()


def record_prediction(db: Session, hospital_id: int, result) -> None:
    """Store the headline of one prediction result.

    History is a convenience, so a failure here is logged and swallowed: a
    clinician who already has a diagnosis must not get an error because the
    bookkeeping row could not be written.
    """
    try:
        db.add(Prediction(
            hospital_id=hospital_id,
            model_id=(getattr(result, "model_id", "") or "")[:32],
            predicted_class=str(result.predicted_class)[:64],
            confidence=float(result.confidence),
            uncertainty=float(getattr(result, "uncertainty", 0.0) or 0.0),
            is_unknown=bool(result.is_unknown),
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not record prediction history for hospital_id=%s", hospital_id)

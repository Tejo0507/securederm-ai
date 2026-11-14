"""A hospital's portable copy of its own data.

Everything the platform holds about an account that is not a secret: the
profile, dataset records, prediction history and the audit trail. Password
hashes, tokens and uploaded images are deliberately not part of it.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from web_backend.audit import read_account_events
from web_backend.db_models import Dataset, Hospital
from web_backend.prediction_history import MAX_EXPORT_ROWS, history_query, serialize_prediction

MAX_ACTIVITY_EVENTS = 1000


def build_data_export(db: Session, hospital: Hospital) -> dict:
    predictions = history_query(db, hospital.id).limit(MAX_EXPORT_ROWS).all()
    datasets = db.query(Dataset).filter(Dataset.hospital_id == hospital.id).order_by(Dataset.id)
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": {
            "id": hospital.id,
            "name": hospital.name,
            "email": hospital.email,
            "location": hospital.location,
            "email_verified": hospital.email_verified,
            "created_at": hospital.created_at.isoformat() if hospital.created_at else None,
        },
        "datasets": [
            {
                "name": d.name,
                "image_count": d.image_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in datasets
        ],
        "predictions": [serialize_prediction(p) for p in predictions],
        "activity": read_account_events(hospital, MAX_ACTIVITY_EVENTS),
    }

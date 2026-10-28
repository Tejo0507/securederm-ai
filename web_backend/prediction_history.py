"""Per-hospital prediction history.

A hospital can review how the model has been used on its account — how many
diagnoses, which classes, how often the model said "unknown" — without the
platform ever keeping a patient image or a diagnosis tied to a person.
"""

import logging

from sqlalchemy.orm import Session

from web_backend.db_models import Prediction

logger = logging.getLogger("web_backend.history")


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

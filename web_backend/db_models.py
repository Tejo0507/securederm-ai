"""Database tables.

Columns are declared with ``Mapped[...]`` so a type checker sees the value a
row holds (``hospital.id`` is an ``int``) rather than the ``Column`` object.
``nullable`` is spelled out wherever the table allows NULL but the annotation
does not, so the schema never changes just because a type hint did.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from web_backend.database import Base


def _utcnow() -> datetime:
    """Naive UTC, matching what SQLite's CURRENT_TIMESTAMP stores."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Hospital(Base):
    __tablename__ = "hospitals"
    # Without AUTOINCREMENT, SQLite gives a new row max(id) + 1, so deleting
    # the newest account hands its id to the next signup, along with every
    # file, rate-limit bucket and log line keyed by it. This only shapes
    # newly created databases; existing ones rely on the created_at checks
    # in auth.get_current_hospital and audit.read_account_events.
    __table_args__ = {"sqlite_autoincrement": True}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(String(200), default="", nullable=True)
    # Set in Python rather than by SQLite's CURRENT_TIMESTAMP, which keeps
    # whole seconds only: session checks compare it with a token's
    # fractional issue time (see auth.get_current_hospital).
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=_utcnow, server_default=func.now()
    )

    # ── Email verification ──────────────────────────────────────────
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_token_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    email_verification_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Session tokens issued before this unix time are rejected ("sign out
    # everywhere"). Null means no such cut-off has ever been set.
    sessions_valid_after: Mapped[Optional[float]] = mapped_column(Float)


class RevokedToken(Base):
    """Session tokens invalidated before their natural expiry (logout,
    password change, account deletion). Stateless tokens otherwise stay
    valid until they expire, even after the user logs out."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[float] = mapped_column(Float, index=True)   # unix time; prune after this


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hospital_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), default="", nullable=True)
    dataset_path: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class MLModel(Base):
    __tablename__ = "ml_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), index=True
    )
    accuracy: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=True)
    hospital_count: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class Prediction(Base):
    """One diagnosis made through the web app.

    Holds only what is needed to review model usage over time: which hospital
    ran it, which checkpoint answered, and the headline result. The image, its
    filename and the per-class probabilities are never stored.
    """
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hospital_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), index=True
    )
    model_id: Mapped[str] = mapped_column(String(32), default="", nullable=True)
    predicted_class: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    uncertainty: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    is_unknown: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )


class FederatedRound(Base):
    __tablename__ = "federated_rounds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    participating_hospitals: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    avg_loss: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

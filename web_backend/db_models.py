from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func

from web_backend.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(500), nullable=False)
    location = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())

    # ── Email verification ──────────────────────────────────────────
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verification_token_hash = Column(String(128), nullable=True, index=True)
    email_verification_expires_at = Column(DateTime, nullable=True)


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(
        Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(200), default="")
    dataset_path = Column(String(500), default="")
    image_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class MLModel(Base):
    __tablename__ = "ml_models"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(200), nullable=False)
    version = Column(Integer, default=1)
    created_by = Column(
        Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    accuracy = Column(Float, default=0.0)
    description = Column(Text, default="")
    hospital_count = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())


class FederatedRound(Base):
    __tablename__ = "federated_rounds"
    id = Column(Integer, primary_key=True, index=True)
    round_number = Column(Integer, nullable=False)
    participating_hospitals = Column(String(500), default="")
    avg_loss = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())

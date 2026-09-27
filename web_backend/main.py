"""
SecureDerm AI — Web Platform Backend.

Run with:
    python -m web_backend.main
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web_backend.database import engine, Base, SessionLocal
from web_backend.db_models import MLModel
from web_backend.routers import auth_router, hospital_router, training_router

Base.metadata.create_all(bind=engine)


def _seed_models() -> None:
    """Populate the marketplace with sample models on first run."""
    db = SessionLocal()
    if db.query(MLModel).count() == 0:
        samples = [
            MLModel(
                model_name="Wound Type Classifier v1",
                version=1,
                accuracy=0.72,
                description="Classifies 10 wound types including burns, surgical wounds, and pressure ulcers. Trained across 2 hospital nodes with differential privacy.",
                hospital_count=2,
            ),
            MLModel(
                model_name="Surgical Infection Detector v2",
                version=2,
                accuracy=0.81,
                description="Detects early signs of surgical wound infection. Federated model trained by 5 hospitals with 4,200 annotated images.",
                hospital_count=5,
            ),
            MLModel(
                model_name="Diabetic Ulcer Severity Model",
                version=1,
                accuracy=0.76,
                description="Grades diabetic foot ulcer severity from stage 1–4. Privacy-preserving training ensures patient data never leaves hospital networks.",
                hospital_count=3,
            ),
            MLModel(
                model_name="Burn Depth Estimator",
                version=3,
                accuracy=0.69,
                description="Estimates burn depth (superficial, partial, full thickness) from wound photographs. Edge-deployable for field triage.",
                hospital_count=4,
            ),
            MLModel(
                model_name="Pressure Wound Risk Predictor",
                version=1,
                accuracy=0.84,
                description="Predicts pressure wound formation risk based on wound area imaging. Top-performing federated model in the SecureDerm network.",
                hospital_count=8,
            ),
        ]
        db.add_all(samples)
        db.commit()
    db.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    _seed_models()
    yield


app = FastAPI(title="SecureDerm AI Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(hospital_router.router, prefix="/api", tags=["hospital"])
app.include_router(training_router.router, prefix="/api", tags=["training"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "SecureDerm AI Platform"}


if __name__ == "__main__":
    uvicorn.run(
        "web_backend.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )

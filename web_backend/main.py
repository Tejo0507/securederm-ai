"""
SecureDerm AI — Web Platform Backend.

Run with:
    python -m web_backend.main

Environment variables (all optional, safe defaults for local dev):
    ENV             "development" (default) or "production". Production
                    disables uvicorn's autoreload and hides error internals.
    HOST            interface to bind. Defaults to 127.0.0.1 (loopback
                    only) — set to 0.0.0.0 explicitly to accept
                    connections from other machines on the network.
    PORT            defaults to 8001.
    CORS_ORIGINS    comma-separated list of allowed frontend origins.
"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from web_backend.database import engine, Base, SessionLocal, run_migrations
from web_backend.db_models import MLModel
from web_backend.routers import auth_router, hospital_router, training_router, predict_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("web_backend")

IS_PRODUCTION = os.getenv("ENV", "development").lower() == "production"
MAX_REQUEST_BODY_BYTES = 25 * 1024 * 1024  # 25 MB — generous over the 10 MB per-file upload cap

Base.metadata.create_all(bind=engine)
run_migrations()


def _seed_models() -> None:
    """Populate the marketplace with sample models on first run."""
    db = SessionLocal()
    if db.query(MLModel).count() == 0:
        samples = [
            MLModel(
                model_name="Wound Type Classifier v1",
                version=1,
                accuracy=0.72,
                description=(
                    "Classifies 10 wound types including burns, surgical wounds, and "
                    "pressure ulcers. Trained across 2 hospital nodes with differential "
                    "privacy."
                ),
                hospital_count=2,
            ),
            MLModel(
                model_name="Surgical Infection Detector v2",
                version=2,
                accuracy=0.81,
                description=(
                    "Detects early signs of surgical wound infection. Federated model "
                    "trained by 5 hospitals with 4,200 annotated images."
                ),
                hospital_count=5,
            ),
            MLModel(
                model_name="Diabetic Ulcer Severity Model",
                version=1,
                accuracy=0.76,
                description=(
                    "Grades diabetic foot ulcer severity from stage 1-4. Privacy-preserving "
                    "training ensures patient data never leaves hospital networks."
                ),
                hospital_count=3,
            ),
            MLModel(
                model_name="Burn Depth Estimator",
                version=3,
                accuracy=0.69,
                description=(
                    "Estimates burn depth (superficial, partial, full thickness) from "
                    "wound photographs. Edge-deployable for field triage."
                ),
                hospital_count=4,
            ),
            MLModel(
                model_name="Pressure Wound Risk Predictor",
                version=1,
                accuracy=0.84,
                description=(
                    "Predicts pressure wound formation risk based on wound area imaging. "
                    "Top-performing federated model in the SecureDerm network."
                ),
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


app = FastAPI(
    title="SecureDerm AI Platform",
    version="1.0.0",
    lifespan=lifespan,
    # Don't expose interactive API docs / schema on a production deployment
    # — they're a convenient map of every endpoint for an attacker.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

_default_cors_origins = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in os.getenv("CORS_ORIGINS", _default_cors_origins).split(",") if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _security_headers_and_body_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})

    response = await call_next(request)

    # Defense-in-depth headers appropriate for a same-origin API server.
    # CSP is deliberately restrictive: this backend only ever serves JSON
    # (and cookies), never HTML it renders itself, so there's no reason to
    # allow any script/style source at all.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(hospital_router.router, prefix="/api", tags=["hospital"])
app.include_router(training_router.router, prefix="/api", tags=["training"])
app.include_router(predict_router.router, prefix="/api", tags=["predict"])


@app.exception_handler(RequestValidationError)
async def readable_validation_error(request: Request, exc: RequestValidationError):
    """FastAPI's default 422 body is {"detail": [{"loc", "msg", "type"}, ...]}.
    The frontend (and any other API consumer) expects `detail` to be a
    plain string to show to the user; left as-is, a validation failure on
    signup/login renders as the literal text "[object Object]" instead of
    e.g. "Password too common". Flatten it to the first, most relevant
    message instead."""
    first_error = exc.errors()[0]
    field = first_error["loc"][-1] if first_error["loc"] else "input"
    message = first_error["msg"]
    return JSONResponse(
        status_code=422,
        content={"detail": f"{field}: {message}"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never let a raw traceback / exception message reach the client —
    it can leak file paths, query text, or other internals. Log the real
    thing server-side and return a generic message instead."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "SecureDerm AI Platform"}


if __name__ == "__main__":
    uvicorn.run(
        "web_backend.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8001")),
        reload=not IS_PRODUCTION,
    )

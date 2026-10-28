"""Wound-image prediction endpoint.

model/inference.py has documented this as the web backend's prediction
path since it was written, but no route ever actually called it — the
endpoint didn't exist. This wires it up.
"""

import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from PIL import Image
from sqlalchemy.orm import Session

from config.settings import PREDICT_RATE_LIMIT_PER_MINUTE
from web_backend.audit import audit
from web_backend.auth import enforce_account_rate_limit, get_current_hospital, verify_csrf
from web_backend.database import get_db
from web_backend.db_models import Hospital
from web_backend.prediction_history import record_prediction
from web_backend.image_validation import MAX_FILE_SIZE_BYTES, is_genuine_image

logger = logging.getLogger("web_backend.predict")

router = APIRouter()


@router.post("/predict")
def predict_wound(  # sync def: FastAPI runs this in a worker thread, so a
    # slow CPU-bound PyTorch forward pass doesn't block the event loop
    # (and therefore every other in-flight request) while it runs.
    request: Request,
    file: UploadFile = File(...),
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    verify_csrf(request)
    enforce_account_rate_limit(hospital.id, "predict", PREDICT_RATE_LIMIT_PER_MINUTE)

    content = file.file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB).")
    if not content or not is_genuine_image(content):
        raise HTTPException(status_code=400, detail="File is not a valid image.")

    # Imported lazily so importing this router (and therefore the whole
    # app) doesn't force a torch/torchvision import and model-checkpoint
    # load path resolution before we know a request actually needs it.
    from model.inference import get_predictor

    try:
        predictor = get_predictor()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="No trained model is available yet. Run federated training first.",
        )

    try:
        image = Image.open(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode image.")

    try:
        result = predictor.predict(image)
    except Exception:
        logger.exception("Prediction failed for hospital_id=%s", hospital.id)
        raise HTTPException(status_code=500, detail="Prediction failed.")

    # Record that a prediction happened and which model made it — never the
    # image or the diagnosis text.
    audit("prediction", hospital.id, model_id=getattr(result, "model_id", None),
          unknown=bool(result.is_unknown))
    record_prediction(db, hospital.id, result)

    return _serialize_result(result)


def _serialize_result(result) -> dict:
    return {
        "model_id": getattr(result, "model_id", None),
        "predicted_class": result.predicted_class,
        "confidence": result.confidence,
        "is_unknown": result.is_unknown,
        "message": result.message,
        "class_probabilities": result.class_probabilities,
        "top_predictions": getattr(result, "top_predictions", []),
        "uncertainty": getattr(result, "uncertainty", 0.0),
    }


MAX_BATCH_IMAGES = 10


@router.post("/predict/batch")
def predict_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """Classify several images in one request.

    Each file is validated on its own: a bad one is reported in its slot with
    an `error` and does not stop the others. Results come back in upload
    order, and every file counts against the account's per-minute limit.
    """
    verify_csrf(request)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > MAX_BATCH_IMAGES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many images in one request (max {MAX_BATCH_IMAGES}).",
        )
    enforce_account_rate_limit(
        hospital.id, "predict", PREDICT_RATE_LIMIT_PER_MINUTE, cost=len(files)
    )

    slots: list[dict] = [{} for _ in files]
    images: list[tuple[int, Image.Image]] = []
    for index, upload in enumerate(files):
        content = upload.file.read(MAX_FILE_SIZE_BYTES + 1)
        if len(content) > MAX_FILE_SIZE_BYTES:
            slots[index] = {"index": index, "error": "Image too large (max 10 MB)."}
        elif not content or not is_genuine_image(content):
            slots[index] = {"index": index, "error": "File is not a valid image."}
        else:
            try:
                image = Image.open(io.BytesIO(content))
                image.load()
                images.append((index, image))
            except Exception:
                slots[index] = {"index": index, "error": "Could not decode image."}

    if not images:
        raise HTTPException(status_code=400, detail="None of the files is a valid image.")

    from model.inference import get_predictor

    try:
        predictor = get_predictor()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="No trained model is available yet. Run federated training first.",
        )

    try:
        results = predictor.predict_batch([image for _, image in images])
    except Exception:
        logger.exception("Batch prediction failed for hospital_id=%s", hospital.id)
        raise HTTPException(status_code=500, detail="Prediction failed.")

    for (index, _), result in zip(images, results):
        audit("prediction", hospital.id, model_id=getattr(result, "model_id", None),
              unknown=bool(result.is_unknown))
        record_prediction(db, hospital.id, result)
        slots[index] = {"index": index, **_serialize_result(result)}

    return {"count": len(images), "failed": len(files) - len(images), "results": slots}

"""Wound-image prediction endpoint.

model/inference.py has documented this as the web backend's prediction
path since it was written, but no route ever actually called it — the
endpoint didn't exist. This wires it up.
"""

import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from PIL import Image

from web_backend.auth import get_current_hospital, verify_csrf
from web_backend.db_models import Hospital
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
):
    verify_csrf(request)

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

    return {
        "predicted_class": result.predicted_class,
        "confidence": result.confidence,
        "is_unknown": result.is_unknown,
        "message": result.message,
        "class_probabilities": result.class_probabilities,
        "top_predictions": getattr(result, "top_predictions", []),
        "uncertainty": getattr(result, "uncertainty", 0.0),
    }

import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from web_backend.database import get_db
from web_backend.db_models import Hospital, Dataset, MLModel
from web_backend.auth import get_current_hospital

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB per image
MAX_FILES_PER_REQUEST = 100
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "BMP", "TIFF", "WEBP"}

router = APIRouter()


def _is_genuine_image(content: bytes) -> bool:
    """Verify file content is really a decodable image, not just a spoofed
    Content-Type header on arbitrary bytes."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        # verify() can leave the parser in a state that can't decode
        # pixel data afterwards, so re-open for a real format check.
        with Image.open(io.BytesIO(content)) as img:
            return img.format in ALLOWED_IMAGE_FORMATS
    except (UnidentifiedImageError, OSError, ValueError):
        return False


@router.post("/datasets/upload")
async def upload_dataset(
    files: list[UploadFile] = File(...),
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files in one request (max {MAX_FILES_PER_REQUEST}).",
        )

    hospital_dir = UPLOAD_DIR / str(hospital.id)
    hospital_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for f in files:
        if not f.filename:
            continue

        content = await f.read(MAX_FILE_SIZE_BYTES + 1)
        if len(content) > MAX_FILE_SIZE_BYTES:
            continue  # reject oversized file, keep processing the rest
        if not content or not _is_genuine_image(content):
            continue  # reject empty / spoofed-content-type / non-image files

        safe_name = Path(f.filename).name
        if not safe_name:
            continue
        dest = hospital_dir / safe_name
        with open(dest, "wb") as out:
            out.write(content)
        saved += 1

    ds = db.query(Dataset).filter(Dataset.hospital_id == hospital.id).first()
    if ds:
        ds.image_count += saved
    else:
        ds = Dataset(
            hospital_id=hospital.id,
            name=f"{hospital.name} Dataset",
            dataset_path=str(hospital_dir),
            image_count=saved,
        )
        db.add(ds)
    db.commit()

    return {"uploaded": saved, "total_images": ds.image_count}


@router.get("/datasets")
async def list_datasets(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    datasets = db.query(Dataset).filter(Dataset.hospital_id == hospital.id).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "image_count": d.image_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]


@router.get("/models")
async def list_models(db: Session = Depends(get_db)):
    models = db.query(MLModel).order_by(MLModel.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "model_name": m.model_name,
            "version": m.version,
            "accuracy": m.accuracy,
            "description": m.description,
            "hospital_count": m.hospital_count,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in models
    ]


@router.get("/hospitals")
async def list_hospitals(db: Session = Depends(get_db)):
    hospitals = db.query(Hospital).all()
    return [
        {"id": h.id, "name": h.name, "location": h.location}
        for h in hospitals
    ]

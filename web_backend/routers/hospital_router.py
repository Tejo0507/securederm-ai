import os
from pathlib import Path, PureWindowsPath

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from sqlalchemy.orm import Session

from web_backend.database import get_db
from web_backend.db_models import Hospital, Dataset, MLModel
from web_backend.auth import get_current_hospital, verify_csrf
from web_backend.image_validation import MAX_FILE_SIZE_BYTES, is_genuine_image

# Overridable so tests can point uploads at a throwaway directory instead
# of writing real files into the project's own datasets/uploads/ on every
# run — the same isolation problem DATABASE_URL had before it was fixed.
_DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "uploads"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(_DEFAULT_UPLOAD_DIR)))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILES_PER_REQUEST = 100
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

router = APIRouter()


@router.post("/datasets/upload")
async def upload_dataset(
    request: Request,
    files: list[UploadFile] = File(...),
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    verify_csrf(request)
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
        if not content or not is_genuine_image(content):
            continue  # reject empty / spoofed-content-type / non-image files

        # PureWindowsPath splits on both "/" and "\", so a client-supplied
        # "..\\..\\x.png" is reduced to its basename on any host OS.
        safe_name = PureWindowsPath(f.filename).name
        if not safe_name or safe_name in (".", ".."):
            continue
        dest = hospital_dir / safe_name
        with open(dest, "wb") as out:
            out.write(content)
        saved += 1

    # Recomputed from what's actually on disk rather than incremented by
    # `saved` — a file whose name collides with one already uploaded
    # (a re-upload, or just a repeated filename across two batches)
    # overwrites the existing file, so incrementing by `saved` would
    # count it twice: image_count would climb past the real number of
    # files in the directory. This also self-heals if the two ever
    # drifted apart for any other reason.
    actual_count = sum(1 for p in hospital_dir.iterdir() if p.is_file())

    ds = db.query(Dataset).filter(Dataset.hospital_id == hospital.id).first()
    if ds:
        ds.image_count = actual_count
    else:
        ds = Dataset(
            hospital_id=hospital.id,
            name=f"{hospital.name} Dataset",
            dataset_path=str(hospital_dir),
            image_count=actual_count,
        )
        db.add(ds)
    db.commit()

    return {"uploaded": saved, "total_images": ds.image_count}


@router.get("/datasets")
async def list_datasets(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    datasets = (
        db.query(Dataset)
        .filter(Dataset.hospital_id == hospital.id)
        .order_by(Dataset.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
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
async def list_models(
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    models = (
        db.query(MLModel)
        .order_by(MLModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
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
async def list_hospitals(
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    hospitals = db.query(Hospital).order_by(Hospital.id).offset(offset).limit(limit).all()
    return [
        {"id": h.id, "name": h.name, "location": h.location}
        for h in hospitals
    ]

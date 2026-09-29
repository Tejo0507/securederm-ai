from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web_backend.database import get_db
from web_backend.db_models import Hospital
from web_backend.schemas import HospitalSignup, HospitalLogin, HospitalResponse
from web_backend.auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_hospital,
    enforce_auth_rate_limit,
    set_session_cookies,
    clear_session_cookies,
    verify_csrf,
    DUMMY_PASSWORD_HASH,
)

router = APIRouter()


@router.post("/signup", response_model=HospitalResponse)
async def signup(
    payload: HospitalSignup,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    enforce_auth_rate_limit(request, "signup")
    existing = db.query(Hospital).filter(Hospital.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hospital = Hospital(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        location=payload.location,
    )
    db.add(hospital)
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent signups for the same email can both pass the
        # existence check above before either commits; the database's
        # unique constraint on email is the real guard, so a violation
        # here means someone won the race, not a server error.
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    db.refresh(hospital)

    token = create_token({"hospital_id": hospital.id, "email": hospital.email})
    set_session_cookies(response, token)
    return HospitalResponse(
        id=hospital.id,
        name=hospital.name,
        email=hospital.email,
        location=hospital.location,
    )


@router.post("/login", response_model=HospitalResponse)
async def login(
    payload: HospitalLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    enforce_auth_rate_limit(request, "login")
    hospital = db.query(Hospital).filter(Hospital.email == payload.email).first()
    # Always run the (expensive) password check, even for an email that
    # isn't registered, against a fixed dummy hash — otherwise a missing
    # account short-circuits and responds measurably faster than a wrong
    # password does, letting an attacker enumerate registered emails by
    # timing the login endpoint.
    hash_to_check = hospital.password_hash if hospital else DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, hash_to_check)
    if not hospital or not password_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"hospital_id": hospital.id, "email": hospital.email})
    set_session_cookies(response, token)
    return HospitalResponse(
        id=hospital.id,
        name=hospital.name,
        email=hospital.email,
        location=hospital.location,
    )


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    hospital: Hospital = Depends(get_current_hospital),
):
    verify_csrf(request)
    clear_session_cookies(response)
    return {"status": "logged_out"}


@router.get("/me")
async def get_me(hospital: Hospital = Depends(get_current_hospital)):
    return {
        "id": hospital.id,
        "name": hospital.name,
        "email": hospital.email,
        "location": hospital.location,
    }

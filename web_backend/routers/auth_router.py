import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.settings import EMAIL_SENDING_CONFIGURED
from web_backend.database import get_db
from web_backend.db_models import Dataset, Hospital, MLModel
from web_backend.email_service import send_verification_email
from web_backend.routers.hospital_router import wipe_hospital_files
from web_backend.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    HospitalSignup,
    HospitalLogin,
    HospitalResponse,
    SignupResponse,
    VerifyEmailRequest,
    ResendVerificationRequest,
)
from web_backend.auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_hospital,
    enforce_auth_rate_limit,
    set_session_cookies,
    clear_session_cookies,
    revoke_session_token,
    SESSION_COOKIE_NAME,
    verify_csrf,
    generate_email_verification_token,
    hash_email_verification_token,
    email_verification_expiry,
    DUMMY_PASSWORD_HASH,
)

router = APIRouter()

# The per-IP rate limit alone lets an attacker spread requests over many IPs
# to flood one victim's inbox with verification mail. Also throttle per
# address. In-memory, like the IP limiter: adequate for one instance.
RESEND_COOLDOWN_SECONDS = 60
_last_resend: dict[str, float] = {}


def _resend_allowed(email: str) -> bool:
    now = time.time()
    if len(_last_resend) > 10_000:   # keep the table bounded
        for key in [k for k, t in _last_resend.items() if now - t > RESEND_COOLDOWN_SECONDS]:
            del _last_resend[key]
    last = _last_resend.get(email)
    if last is not None and now - last < RESEND_COOLDOWN_SECONDS:
        return False
    _last_resend[email] = now
    return True


def _hospital_response(hospital: Hospital) -> HospitalResponse:
    return HospitalResponse(
        id=hospital.id,
        name=hospital.name,
        email=hospital.email,
        location=hospital.location,
        email_verified=hospital.email_verified,
    )


async def _issue_verification(hospital: Hospital, db: Session) -> str:
    """(Re)issue a verification token for `hospital`, persist its hash, and
    send/log the email. Returns the raw token only for dev-mode echoing."""
    token = generate_email_verification_token()
    hospital.email_verification_token_hash = hash_email_verification_token(token)
    hospital.email_verification_expires_at = email_verification_expiry()
    db.commit()
    # smtplib is blocking (up to its 10s timeout per attempt); run it in a
    # worker thread so a slow mail server doesn't stall every other
    # request on the event loop.
    await run_in_threadpool(
        send_verification_email, hospital.email, hospital.name, token
    )
    return token


@router.post("/signup", response_model=SignupResponse)
async def signup(
    payload: HospitalSignup,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_auth_rate_limit(request, "signup")
    existing = db.query(Hospital).filter(Hospital.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hospital = Hospital(
        name=payload.name,
        email=payload.email,
        # 600k PBKDF2 rounds take a few hundred ms of pure CPU; run inline in
        # an async handler it would freeze every other request meanwhile.
        password_hash=await run_in_threadpool(hash_password, payload.password),
        location=payload.location,
        email_verified=False,
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

    # No session cookie yet: signing up only proves someone typed an
    # email-shaped string, not that they can read mail sent to it. A
    # session is issued once /verify-email confirms that.
    token = await _issue_verification(hospital, db)
    return SignupResponse(
        status="verification_email_sent",
        email=hospital.email,
        dev_verification_token=None if EMAIL_SENDING_CONFIGURED else token,
    )


@router.post("/verify-email", response_model=HospitalResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    enforce_auth_rate_limit(request, "verify-email")
    token_hash = hash_email_verification_token(payload.token)
    hospital = (
        db.query(Hospital)
        .filter(Hospital.email_verification_token_hash == token_hash)
        .first()
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if (
        hospital is None
        or hospital.email_verification_expires_at is None
        or hospital.email_verification_expires_at < now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")

    hospital.email_verified = True
    hospital.email_verification_token_hash = None
    hospital.email_verification_expires_at = None
    db.commit()
    db.refresh(hospital)

    # Verifying proves inbox ownership, which is exactly the bar for
    # trusting this session — log them straight in rather than making
    # them turn around and enter their password again.
    session_token = create_token({"hospital_id": hospital.id, "email": hospital.email})
    set_session_cookies(response, session_token)
    return _hospital_response(hospital)


@router.post("/resend-verification")
async def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_auth_rate_limit(request, "resend-verification")
    hospital = db.query(Hospital).filter(Hospital.email == payload.email).first()

    dev_token = None
    if hospital is not None and not hospital.email_verified and _resend_allowed(hospital.email):
        dev_token = await _issue_verification(hospital, db)

    # Same response whether the account exists, is already verified, or
    # never existed at all — otherwise this endpoint becomes a free tool
    # for checking which emails have (unverified) accounts.
    return {
        "status": "if_account_exists_email_sent",
        "dev_verification_token": None if EMAIL_SENDING_CONFIGURED else dev_token,
    }


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
    password_ok = await run_in_threadpool(verify_password, payload.password, hash_to_check)
    if not hospital or not password_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not hospital.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Check your inbox, or request a new link.",
        )

    token = create_token({"hospital_id": hospital.id, "email": hospital.email})
    set_session_cookies(response, token)
    return _hospital_response(hospital)


@router.post("/logout")
async def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    # Deliberately does not require a *valid* session: with an expired or
    # revoked one, a get_current_hospital dependency answered 401 and the
    # stale cookies could never be cleared. CSRF is still enforced whenever
    # a session cookie is actually present, so a third-party page can't
    # silently log a user out.
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if session_cookie:
        verify_csrf(request)
        # Stateless tokens would otherwise stay usable until they expire,
        # even for someone who copied the cookie before the user logged out.
        revoke_session_token(db, session_cookie)
    clear_session_cookies(response)
    return {"status": "logged_out"}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    verify_csrf(request)
    enforce_auth_rate_limit(request, "change-password")
    ok = await run_in_threadpool(verify_password, payload.current_password, hospital.password_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    hospital.password_hash = await run_in_threadpool(hash_password, payload.new_password)
    db.commit()
    # The old session may be in someone else's hands; end it and make the
    # user sign in again with the new password.
    revoke_session_token(db, request.cookies.get(SESSION_COOKIE_NAME))
    clear_session_cookies(response)
    return {"status": "password_changed"}


@router.delete("/account")
async def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    """Permanently delete the hospital, its uploaded images and dataset records.

    Requires the password again, so a hijacked session alone cannot destroy
    an account.
    """
    verify_csrf(request)
    enforce_auth_rate_limit(request, "delete-account")
    ok = await run_in_threadpool(verify_password, payload.password, hospital.password_hash)
    if not ok:
        raise HTTPException(status_code=401, detail="Password is incorrect")

    hospital_id = hospital.id
    revoke_session_token(db, request.cookies.get(SESSION_COOKIE_NAME))
    db.query(Dataset).filter(Dataset.hospital_id == hospital_id).delete()
    db.query(MLModel).filter(MLModel.created_by == hospital_id).update({MLModel.created_by: None})
    db.delete(hospital)
    db.commit()
    wipe_hospital_files(hospital_id)
    clear_session_cookies(response)
    return {"status": "account_deleted"}


@router.get("/me", response_model=HospitalResponse)
async def get_me(hospital: Hospital = Depends(get_current_hospital)):
    return _hospital_response(hospital)

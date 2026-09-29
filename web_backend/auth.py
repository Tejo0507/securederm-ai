import hashlib
import hmac
import os
import secrets
import time
import json
import base64
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from config.settings import JWT_SECRET
from web_backend.database import get_db
from web_backend.db_models import Hospital

SECRET_KEY = JWT_SECRET
TOKEN_EXPIRY = 86400  # 24 hours

# ── Session cookie configuration ─────────────────────────────────────────
# Sessions live in an httpOnly cookie instead of being handed to
# JavaScript (localStorage), so a successful XSS on the frontend can no
# longer just read the token out and exfiltrate it. `secure=True` is safe
# in local dev too: browsers treat http://localhost as a secure context.
SESSION_COOKIE_NAME = "session_token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Cookies only protect against CSRF via SameSite when the frontend and
# API are same-site (as they are here: localhost:3000 / localhost:8001
# share a registrable domain). A cross-domain production deployment would
# need SameSite="none" + Secure, at which point the double-submit CSRF
# check below (verify_csrf) becomes the only thing stopping cross-site
# requests from riding an authenticated user's cookies — so it is applied
# unconditionally, not just as a SameSite fallback.
_COOKIE_SAMESITE = "lax"


def set_session_cookies(response: Response, token: str) -> None:
    """Issue the httpOnly session cookie plus its paired, JS-readable
    CSRF cookie (double-submit pattern) after a successful login/signup."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRY,
        httponly=True,
        secure=True,
        samesite=_COOKIE_SAMESITE,
        path="/",
    )
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=TOKEN_EXPIRY,
        httponly=False,  # must be readable by frontend JS to echo back
        secure=True,
        samesite=_COOKIE_SAMESITE,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def verify_csrf(request: Request) -> None:
    """Double-submit CSRF check for state-changing requests: the value a
    cross-site attacker's form/fetch cannot read (the cookie) must match
    a value they also cannot set on our behalf (a custom request header,
    which triggers a CORS preflight that our origin allowlist blocks)."""
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_value or not header_value or not secrets.compare_digest(
        cookie_value, header_value
    ):
        raise HTTPException(status_code=403, detail="CSRF check failed.")


# ── Simple in-memory rate limiting for auth endpoints ────────────────────
# Not shared across worker processes and resets on restart — adequate to
# blunt naive credential-stuffing / brute-force scripts against a single
# instance, but a real multi-process deployment should back this with
# Redis (already a project dependency) instead.
_RATE_LIMIT_WINDOW_SECONDS = 300
_RATE_LIMIT_MAX_ATTEMPTS = 10
_auth_attempts: dict[str, deque] = defaultdict(deque)


def enforce_auth_rate_limit(request: Request, bucket: str) -> None:
    client_host = request.client.host if request.client else "unknown"
    key = f"{bucket}:{client_host}"
    now = time.time()
    attempts = _auth_attempts[key]

    while attempts and now - attempts[0] > _RATE_LIMIT_WINDOW_SECONDS:
        attempts.popleft()

    if len(attempts) >= _RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please try again later.",
        )

    attempts.append(now)


# OWASP's 2023 minimum for PBKDF2-HMAC-SHA256. The iteration count is
# encoded into every new hash (django-style "algorithm$iterations$salt$hash")
# specifically so it can be raised again later without invalidating
# passwords hashed under the old count — the previous format
# ("<salt_hex>:<key_hex>") baked 100,000 iterations in implicitly, which
# meant bumping the constant would have silently broken every existing
# login. verify_password still accepts that legacy format.
PBKDF2_ITERATIONS = 600_000
_LEGACY_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, iterations_str, salt_hex, key_hex = stored.split("$")
            iterations = int(iterations_str)
        else:
            salt_hex, key_hex = stored.split(":")
            iterations = _LEGACY_PBKDF2_ITERATIONS
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return hmac.compare_digest(key, bytes.fromhex(key_hex))
    except Exception:
        return False


# A verify_password() call against a real hash takes measurable time
# (hundreds of thousands of PBKDF2 rounds); skipping it entirely when an
# email isn't registered makes "no such account" respond faster than
# "wrong password" — a timing side-channel an attacker can use to
# enumerate which emails have accounts. Hashed once at import so login
# always pays the same cost whether or not the account exists.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def create_token(payload: dict) -> str:
    header = (
        base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        )
        .decode()
        .rstrip("=")
    )
    data = {**payload, "exp": time.time() + TOKEN_EXPIRY}
    body = (
        base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    )
    sig = hmac.new(
        SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256
    ).hexdigest()
    return f"{header}.{body}.{sig}"


def decode_token(token: str) -> dict | None:
    try:
        header, body, sig = token.split(".")
        expected = hmac.new(
            SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = body + "=" * (4 - len(body) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None


async def get_current_hospital(
    request: Request,
    db: Session = Depends(get_db),
) -> Hospital:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    hospital = (
        db.query(Hospital)
        .filter(Hospital.id == payload.get("hospital_id"))
        .first()
    )
    if hospital is None:
        raise HTTPException(status_code=401, detail="Hospital not found")
    return hospital

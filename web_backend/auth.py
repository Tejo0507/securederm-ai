import hashlib
import hmac
import os
import time
import json
import base64
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config.settings import JWT_SECRET
from web_backend.database import get_db
from web_backend.db_models import Hospital

SECRET_KEY = JWT_SECRET
TOKEN_EXPIRY = 86400  # 24 hours

security = HTTPBearer()

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


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return hmac.compare_digest(key, bytes.fromhex(key_hex))
    except Exception:
        return False


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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Hospital:
    token = credentials.credentials
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

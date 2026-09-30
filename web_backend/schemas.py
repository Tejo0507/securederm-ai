from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime

# NIST 800-63B recommends checking new passwords against known-weak /
# breached lists over forcing arbitrary complexity rules (which push
# users toward predictable substitutions like "Password1!"). This is a
# small, deliberately non-exhaustive sample of the passwords that show up
# at the top of every breach-corpus frequency list.
_COMMON_WEAK_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789",
    "1234567890", "qwerty123", "letmein123", "welcome123", "admin1234",
    "iloveyou1", "sunshine1", "princess1", "football1", "baseball1",
    "changeme1", "abc123456", "correcthorsebatterystaple",
}


class HospitalSignup(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    location: str = Field(default="", max_length=200)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        # Prevents "Foo@x.com" and "foo@x.com" registering as distinct
        # hospitals (SQLite's unique index is case-sensitive by default).
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def _reject_common_password(cls, v: str) -> str:
        if v.lower() in _COMMON_WEAK_PASSWORDS:
            raise ValueError(
                "This password is too common. Please choose a less predictable one."
            )
        return v


class HospitalLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class HospitalResponse(BaseModel):
    id: int
    name: str
    email: str
    location: str = ""
    email_verified: bool = False


class SignupResponse(BaseModel):
    status: str
    email: str
    # Only ever populated when no SMTP account is configured server-side
    # (see EMAIL_SENDING_CONFIGURED) — ie. never on a properly configured
    # deployment, where the real verification email is sent instead.
    dev_verification_token: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=500)


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TrainingStart(BaseModel):
    rounds: int = 5

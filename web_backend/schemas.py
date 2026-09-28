from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime


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


class TrainingStart(BaseModel):
    rounds: int = 5

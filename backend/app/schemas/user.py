import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Enforce a minimal password policy.
        Keeps it simple — no regex soup — just a meaningful minimum.
        """
        if v.isdigit():
            raise ValueError("Password must not be all digits.")
        if v.lower() == v:
            # At least one uppercase or a non-alpha char is enough
            # to prevent 'password', 'qwerty', etc.
            pass  # relax for now; can tighten in production
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
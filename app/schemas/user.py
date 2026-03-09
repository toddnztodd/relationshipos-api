"""Pydantic schemas for User authentication and profile."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ── Auth Schemas ───────────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    email: str = Field(..., max_length=255, examples=["todd@eves.co.nz"])
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., max_length=255, examples=["Todd Hilleard"])


class UserLogin(BaseModel):
    email: str = Field(..., examples=["todd@eves.co.nz"])
    password: str = Field(...)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None


# ── User Response ──────────────────────────────────────────────────────────────


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}

"""Pydantic schemas for the Referral Programme."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Embedded person summary ───────────────────────────────────────────────────

class ReferralPersonSummary(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = ""
    phone: Optional[str] = None
    email: Optional[str] = None
    tier: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Register referral member ──────────────────────────────────────────────────

class RegisterReferralMemberRequest(BaseModel):
    reward_amount: Optional[float] = 250.0


class RegisterReferralMemberResponse(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = ""
    email: Optional[str] = None
    referral_member: bool
    referral_reward_amount: float
    referral_email_sent_at: Optional[datetime] = None
    email_sent: bool
    email_sent_reason: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Referral CRUD ─────────────────────────────────────────────────────────────

class ReferralCreate(BaseModel):
    referrer_person_id: int
    referred_person_id: int
    notes: Optional[str] = None


class ReferralUpdate(BaseModel):
    referral_status: Optional[str] = None
    reward_status: Optional[str] = None
    reward_amount: Optional[float] = None
    notes: Optional[str] = None


class ReferralResponse(BaseModel):
    id: int
    user_id: int
    referrer_person_id: int
    referred_person_id: int
    referral_status: str
    reward_amount: float
    reward_status: str
    reward_paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    referrer: Optional[ReferralPersonSummary] = None
    referred: Optional[ReferralPersonSummary] = None

    model_config = {"from_attributes": True}

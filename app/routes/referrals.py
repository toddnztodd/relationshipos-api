"""Referral Programme routes for RelationshipOS."""

import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Activity, InteractionType, Person, Referral, User
from app.services.auth import get_current_user
from app.schemas.referral import (
    ReferralCreate,
    ReferralPersonSummary,
    ReferralResponse,
    ReferralUpdate,
    RegisterReferralMemberRequest,
    RegisterReferralMemberResponse,
)

router = APIRouter(tags=["Referrals"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _log_activity(
    db: AsyncSession,
    user_id: int,
    person_id: int,
    notes: str,
) -> None:
    """Create a system_event activity log entry for a person."""
    activity = Activity(
        user_id=user_id,
        person_id=person_id,
        interaction_type=InteractionType.system_event,
        notes=notes,
        is_meaningful=False,
        date=datetime.now(timezone.utc),
    )
    db.add(activity)


def _try_send_email(
    to_email: str,
    first_name: str,
    reward_amount: float,
    agent_name: str,
) -> tuple[bool, Optional[str]]:
    """
    Attempt to send the referral registration email via SMTP.
    Returns (email_sent: bool, reason: Optional[str]).
    """
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not smtp_host or not smtp_user:
        return False, "No SMTP configured"

    subject = "You're registered in my referral programme"
    body = (
        f"Hi {first_name},\n\n"
        f"I've formally registered you in my ${reward_amount:.0f} referral programme.\n\n"
        f"If you introduce someone who lists and sells their property with me, "
        f"I'll send you ${reward_amount:.0f} as a thank you.\n\n"
        f"Simply pass on my details or let me know who to reach out to.\n\n"
        f"Thanks,\n{agent_name}"
    )

    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        return True, None
    except Exception as exc:
        return False, str(exc)


def _person_to_summary(person: Person) -> ReferralPersonSummary:
    return ReferralPersonSummary(
        id=person.id,
        first_name=person.first_name,
        last_name=person.last_name or "",
        phone=person.phone,
        email=person.email,
        tier=person.tier.value if person.tier else None,
    )


def _referral_to_response(ref: Referral) -> ReferralResponse:
    return ReferralResponse(
        id=ref.id,
        user_id=ref.user_id,
        referrer_person_id=ref.referrer_person_id,
        referred_person_id=ref.referred_person_id,
        referral_status=ref.referral_status,
        reward_amount=float(ref.reward_amount),
        reward_status=ref.reward_status,
        reward_paid_at=ref.reward_paid_at,
        notes=ref.notes,
        created_at=ref.created_at,
        updated_at=ref.updated_at,
        referrer=_person_to_summary(ref.referrer) if ref.referrer else None,
        referred=_person_to_summary(ref.referred) if ref.referred else None,
    )


# ── Register referral member ──────────────────────────────────────────────────

@router.post(
    "/people/{person_id}/register-referral-member",
    response_model=RegisterReferralMemberResponse,
    status_code=200,
)
async def register_referral_member(
    person_id: int,
    body: RegisterReferralMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Person).where(
            Person.id == person_id,
            Person.user_id == current_user.id,
        )
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    reward = body.reward_amount if body.reward_amount is not None else 250.0
    person.referral_member = True
    person.referral_reward_amount = reward

    email_sent = False
    email_reason: Optional[str] = None

    if person.email:
        email_sent, email_reason = _try_send_email(
            to_email=person.email,
            first_name=person.first_name,
            reward_amount=reward,
            agent_name=current_user.full_name,
        )
        if email_sent:
            person.referral_email_sent_at = datetime.now(timezone.utc)
            await _log_activity(
                db, current_user.id, person_id,
                f"Referral programme registration email sent (${reward:.0f} reward)",
            )
        else:
            await _log_activity(
                db, current_user.id, person_id,
                f"Referral programme registered — email failed: {email_reason}",
            )
    else:
        email_reason = "No email address on file"
        await _log_activity(
            db, current_user.id, person_id,
            "Referral programme registered — no email on file",
        )

    await db.flush()
    await db.refresh(person)

    return RegisterReferralMemberResponse(
        id=person.id,
        first_name=person.first_name,
        last_name=person.last_name or "",
        email=person.email,
        referral_member=person.referral_member,
        referral_reward_amount=float(person.referral_reward_amount),
        referral_email_sent_at=person.referral_email_sent_at,
        email_sent=email_sent,
        email_sent_reason=email_reason,
    )


# ── List referrals for a person ───────────────────────────────────────────────

@router.get(
    "/people/{person_id}/referrals",
    response_model=List[ReferralResponse],
)
async def list_person_referrals(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Confirm person belongs to this user
    p_result = await db.execute(
        select(Person).where(
            Person.id == person_id,
            Person.user_id == current_user.id,
        )
    )
    if not p_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Person not found")

    r_result = await db.execute(
        select(Referral).where(
            Referral.user_id == current_user.id,
            or_(
                Referral.referrer_person_id == person_id,
                Referral.referred_person_id == person_id,
            ),
        ).order_by(Referral.created_at.desc())
    )
    refs = r_result.scalars().all()

    responses = []
    for ref in refs:
        if not ref.referrer:
            rr_res = await db.execute(select(Person).where(Person.id == ref.referrer_person_id))
            ref.referrer = rr_res.scalar_one_or_none()
        if not ref.referred:
            rd_res = await db.execute(select(Person).where(Person.id == ref.referred_person_id))
            ref.referred = rd_res.scalar_one_or_none()
        responses.append(_referral_to_response(ref))

    return responses


# ── Create referral ───────────────────────────────────────────────────────────

@router.post("/referrals", response_model=ReferralResponse, status_code=201)
async def create_referral(
    body: ReferralCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate both people belong to this user
    rr_res = await db.execute(
        select(Person).where(
            Person.id == body.referrer_person_id,
            Person.user_id == current_user.id,
        )
    )
    referrer = rr_res.scalar_one_or_none()
    if not referrer:
        raise HTTPException(status_code=404, detail="Referrer person not found")

    rd_res = await db.execute(
        select(Person).where(
            Person.id == body.referred_person_id,
            Person.user_id == current_user.id,
        )
    )
    referred = rd_res.scalar_one_or_none()
    if not referred:
        raise HTTPException(status_code=404, detail="Referred person not found")

    # Check for duplicate
    dup_res = await db.execute(
        select(Referral).where(
            Referral.referrer_person_id == body.referrer_person_id,
            Referral.referred_person_id == body.referred_person_id,
        )
    )
    if dup_res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Referral relationship already exists")

    ref = Referral(
        user_id=current_user.id,
        referrer_person_id=body.referrer_person_id,
        referred_person_id=body.referred_person_id,
        reward_amount=float(referrer.referral_reward_amount) if referrer.referral_reward_amount else 250,
        notes=body.notes,
    )
    db.add(ref)
    await db.flush()

    # Activity logs on both people
    referrer_name = f"{referrer.first_name} {referrer.last_name or ''}".strip()
    referred_name = f"{referred.first_name} {referred.last_name or ''}".strip()

    await _log_activity(
        db, current_user.id, body.referrer_person_id,
        f"Referred {referred_name} to the programme",
    )
    await _log_activity(
        db, current_user.id, body.referred_person_id,
        f"Referred by {referrer_name}",
    )

    await db.flush()
    await db.refresh(ref)

    ref.referrer = referrer
    ref.referred = referred
    return _referral_to_response(ref)


# ── Update referral ───────────────────────────────────────────────────────────

@router.put("/referrals/{referral_id}", response_model=ReferralResponse)
async def update_referral(
    referral_id: int,
    body: ReferralUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_res = await db.execute(
        select(Referral).where(
            Referral.id == referral_id,
            Referral.user_id == current_user.id,
        )
    )
    ref = ref_res.scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Referral not found")

    old_reward_status = ref.reward_status

    if body.referral_status is not None:
        valid_statuses = {"registered", "referral_received", "listing_secured", "sold", "closed"}
        if body.referral_status not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid referral_status. Must be one of: {sorted(valid_statuses)}",
            )
        ref.referral_status = body.referral_status

    if body.reward_status is not None:
        valid_reward = {"none", "pending", "earned", "paid"}
        if body.reward_status not in valid_reward:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid reward_status. Must be one of: {sorted(valid_reward)}",
            )
        ref.reward_status = body.reward_status

        # Side effects on reward status change
        if body.reward_status == "earned" and old_reward_status != "earned":
            await _log_activity(
                db, current_user.id, ref.referrer_person_id,
                f"Referral reward earned — ${float(ref.reward_amount):.0f}",
            )
        elif body.reward_status == "paid" and old_reward_status != "paid":
            ref.reward_paid_at = datetime.now(timezone.utc)
            await _log_activity(
                db, current_user.id, ref.referrer_person_id,
                f"Referral reward paid — ${float(ref.reward_amount):.0f}",
            )

    if body.reward_amount is not None:
        ref.reward_amount = body.reward_amount

    if body.notes is not None:
        ref.notes = body.notes

    ref.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(ref)

    # Load relationships if not present
    if not ref.referrer:
        rr_res = await db.execute(select(Person).where(Person.id == ref.referrer_person_id))
        ref.referrer = rr_res.scalar_one_or_none()
    if not ref.referred:
        rd_res = await db.execute(select(Person).where(Person.id == ref.referred_person_id))
        ref.referred = rd_res.scalar_one_or_none()

    return _referral_to_response(ref)


# ── List all referrals ────────────────────────────────────────────────────────

@router.get("/referrals", response_model=List[ReferralResponse])
async def list_referrals(
    status: Optional[str] = Query(None),
    reward_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Referral).where(Referral.user_id == current_user.id)

    if status:
        query = query.where(Referral.referral_status == status)
    if reward_status:
        query = query.where(Referral.reward_status == reward_status)

    query = query.order_by(Referral.created_at.desc())
    r_result = await db.execute(query)
    refs = r_result.scalars().all()

    responses = []
    for ref in refs:
        if not ref.referrer:
            rr_res = await db.execute(select(Person).where(Person.id == ref.referrer_person_id))
            ref.referrer = rr_res.scalar_one_or_none()
        if not ref.referred:
            rd_res = await db.execute(select(Person).where(Person.id == ref.referred_person_id))
            ref.referred = rd_res.scalar_one_or_none()
        responses.append(_referral_to_response(ref))

    return responses


# ── Soft delete (close) referral ──────────────────────────────────────────────

@router.delete("/referrals/{referral_id}", status_code=200)
async def close_referral(
    referral_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_res = await db.execute(
        select(Referral).where(
            Referral.id == referral_id,
            Referral.user_id == current_user.id,
        )
    )
    ref = ref_res.scalar_one_or_none()
    if not ref:
        raise HTTPException(status_code=404, detail="Referral not found")

    ref.referral_status = "closed"
    ref.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"detail": "Referral closed", "id": referral_id}

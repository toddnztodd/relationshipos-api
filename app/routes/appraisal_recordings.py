"""Appraisal Recordings — CRUD routes for persisting appraisal conversation recordings."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import AppraisalRecording, Property
from app.schemas.appraisal_recording import (
    AppraisalRecordingCreate,
    AppraisalRecordingListResponse,
    AppraisalRecordingResponse,
)
from app.services.auth import get_current_user

# Router scoped under /properties/{property_id}/appraisals
property_router = APIRouter(prefix="/properties", tags=["Appraisal Recordings"])

# Router scoped under /appraisals/{appraisal_id}
appraisal_router = APIRouter(prefix="/appraisals", tags=["Appraisal Recordings"])


# ── POST /properties/{property_id}/appraisals ─────────────────────────────────


@property_router.post(
    "/{property_id}/appraisals",
    response_model=AppraisalRecordingResponse,
    status_code=201,
)
async def create_appraisal_recording(
    property_id: int,
    body: AppraisalRecordingCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new appraisal recording for a property."""
    # Verify the property exists and belongs to the current user
    prop_result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.user_id == current_user.id,
        )
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    recording = AppraisalRecording(
        property_id=property_id,
        user_id=current_user.id,
        audio_url=body.audio_url,
        transcript=body.transcript,
        summary=body.summary,
        extracted_intelligence=body.extracted_intelligence,
        detected_signals=body.detected_signals,
        duration_seconds=body.duration_seconds,
    )
    db.add(recording)
    await db.flush()
    await db.refresh(recording)
    return AppraisalRecordingResponse.model_validate(recording)


# ── GET /properties/{property_id}/appraisals ──────────────────────────────────


@property_router.get(
    "/{property_id}/appraisals",
    response_model=AppraisalRecordingListResponse,
)
async def list_appraisal_recordings(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all appraisal recordings for a property, newest first."""
    # Verify the property exists and belongs to the current user
    prop_result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.user_id == current_user.id,
        )
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(AppraisalRecording)
        .where(
            AppraisalRecording.property_id == property_id,
            AppraisalRecording.user_id == current_user.id,
        )
        .order_by(AppraisalRecording.created_at.desc())
    )
    recordings = result.scalars().all()
    return AppraisalRecordingListResponse(
        recordings=[AppraisalRecordingResponse.model_validate(r) for r in recordings],
        total=len(recordings),
    )


# ── GET /appraisals/{appraisal_id} ───────────────────────────────────────────


@appraisal_router.get(
    "/{appraisal_id}",
    response_model=AppraisalRecordingResponse,
)
async def get_appraisal_recording(
    appraisal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single appraisal recording by ID."""
    result = await db.execute(
        select(AppraisalRecording).where(
            AppraisalRecording.id == appraisal_id,
            AppraisalRecording.user_id == current_user.id,
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="Appraisal recording not found")
    return AppraisalRecordingResponse.model_validate(recording)


# ── DELETE /appraisals/{appraisal_id} ────────────────────────────────────────


@appraisal_router.delete(
    "/{appraisal_id}",
    status_code=200,
)
async def delete_appraisal_recording(
    appraisal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete an appraisal recording."""
    result = await db.execute(
        select(AppraisalRecording).where(
            AppraisalRecording.id == appraisal_id,
            AppraisalRecording.user_id == current_user.id,
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="Appraisal recording not found")

    await db.delete(recording)
    await db.flush()
    return {"detail": "Appraisal recording deleted", "id": appraisal_id}

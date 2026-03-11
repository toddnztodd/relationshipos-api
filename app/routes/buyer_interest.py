"""Buyer Interest — CRUD endpoints for tracking buyer interest in properties."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    BuyerInterest,
    BuyerInterestStage,
    Person,
    Property,
)
from app.schemas.property import (
    BuyerInterestCreate,
    BuyerInterestPersonSummary,
    BuyerInterestResponse,
    BuyerInterestUpdate,
)
from app.services.auth import get_current_user

# /properties/{property_id}/buyer-interest
property_router = APIRouter(prefix="/properties", tags=["Buyer Interest"])

# /buyer-interest/{id}
top_router = APIRouter(prefix="/buyer-interest", tags=["Buyer Interest"])


def _build_response(bi: BuyerInterest) -> BuyerInterestResponse:
    person_summary = None
    if bi.person:
        person_summary = BuyerInterestPersonSummary(
            id=bi.person.id,
            first_name=bi.person.first_name,
            last_name=bi.person.last_name or "",
        )
    return BuyerInterestResponse(
        id=bi.id,
        property_id=bi.property_id,
        person_id=bi.person_id,
        person=person_summary,
        stage=bi.stage.value,
        created_at=bi.created_at,
        updated_at=bi.updated_at,
    )


@property_router.get("/{property_id}/buyer-interest", response_model=List[BuyerInterestResponse])
async def list_buyer_interest(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all buyer interest records for a property."""
    # Verify property belongs to user
    prop_result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    if not prop_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(BuyerInterest)
        .where(BuyerInterest.property_id == property_id, BuyerInterest.user_id == current_user.id)
        .order_by(BuyerInterest.updated_at.desc())
    )
    return [_build_response(bi) for bi in result.scalars().all()]


@property_router.post(
    "/{property_id}/buyer-interest",
    response_model=BuyerInterestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_buyer_interest(
    property_id: int,
    payload: BuyerInterestCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a buyer interest record linking a person to a property."""
    # Verify property
    prop_result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    if not prop_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Property not found")

    # Verify person
    person_result = await db.execute(
        select(Person).where(Person.id == payload.person_id, Person.user_id == current_user.id)
    )
    if not person_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Person not found")

    # Check for duplicate
    existing = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.property_id == property_id,
            BuyerInterest.person_id == payload.person_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Buyer interest already exists for this person and property")

    # Validate stage
    try:
        stage = BuyerInterestStage(payload.stage)
    except ValueError:
        stage = BuyerInterestStage.seen

    bi = BuyerInterest(
        user_id=current_user.id,
        property_id=property_id,
        person_id=payload.person_id,
        stage=stage,
    )
    db.add(bi)
    await db.flush()
    await db.refresh(bi)
    return _build_response(bi)


@top_router.patch("/{interest_id}", response_model=BuyerInterestResponse)
async def update_buyer_interest(
    interest_id: int,
    payload: BuyerInterestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update the stage of a buyer interest record."""
    result = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.id == interest_id,
            BuyerInterest.user_id == current_user.id,
        )
    )
    bi = result.scalar_one_or_none()
    if not bi:
        raise HTTPException(status_code=404, detail="Buyer interest not found")

    try:
        bi.stage = BuyerInterestStage(payload.stage)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid stage: {payload.stage}")

    await db.flush()
    await db.refresh(bi)
    return _build_response(bi)


@top_router.delete("/{interest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_buyer_interest(
    interest_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a buyer interest record."""
    result = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.id == interest_id,
            BuyerInterest.user_id == current_user.id,
        )
    )
    bi = result.scalar_one_or_none()
    if not bi:
        raise HTTPException(status_code=404, detail="Buyer interest not found")
    await db.delete(bi)

"""Structured Listing Checklist routes — 12-phase workflow per property."""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    User,
    Property,
    ListingChecklist,
    ChecklistPhase,
    ChecklistItem,
)
from app.schemas.listing_checklist import (
    ChecklistCreate,
    ChecklistItemUpdate,
    ChecklistItemResponse,
    ChecklistPhaseResponse,
    ChecklistResponse,
    PhaseUpdate,
)
from app.services.auth import get_current_user
from app.services.checklist_templates import PHASE_NAMES, get_template_items

# ── Property-scoped router ───────────────────────────────────────────────────

property_router = APIRouter(prefix="/properties", tags=["Listing Checklist V2"])

# ── Top-level routers ────────────────────────────────────────────────────────

checklists_router = APIRouter(prefix="/checklists", tags=["Listing Checklist V2"])
items_router = APIRouter(prefix="/checklist-items-v2", tags=["Listing Checklist V2"])


# ── Helper: build structured response ────────────────────────────────────────


def _build_checklist_response(cl: ListingChecklist) -> dict:
    """Build a ChecklistResponse dict with items nested under their phases."""
    # Group items by phase_number
    items_by_phase: dict[int, list] = {}
    for item in cl.items:
        items_by_phase.setdefault(item.phase_number, []).append(
            ChecklistItemResponse.model_validate(item)
        )

    phases = []
    for phase in cl.phases:
        phases.append(ChecklistPhaseResponse(
            phase_number=phase.phase_number,
            phase_name=phase.phase_name,
            is_complete=phase.is_complete,
            completed_at=phase.completed_at,
            items=items_by_phase.get(phase.phase_number, []),
        ))

    return ChecklistResponse(
        id=cl.id,
        property_id=cl.property_id,
        sale_method=cl.sale_method,
        current_phase=cl.current_phase,
        phases=phases,
        created_at=cl.created_at,
        updated_at=cl.updated_at,
    )


# ── GET checklist for a property ─────────────────────────────────────────────


@property_router.get(
    "/{property_id}/listing-checklist",
    response_model=ChecklistResponse,
)
async def get_listing_checklist(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the structured listing checklist for a property (or 404)."""
    result = await db.execute(
        select(ListingChecklist).where(
            ListingChecklist.property_id == property_id,
            ListingChecklist.user_id == current_user.id,
        )
    )
    cl = result.scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="No listing checklist found for this property")
    return _build_checklist_response(cl)


# ── POST create checklist with template seeding ──────────────────────────────


@property_router.post(
    "/{property_id}/listing-checklist",
    response_model=ChecklistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_listing_checklist(
    property_id: int,
    payload: ChecklistCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a structured 12-phase listing checklist for a property.

    Seeds default items from the template based on sale_method.
    Only one checklist per property is allowed.
    """
    # Validate property
    prop = (await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check for existing checklist
    existing = (await db.execute(
        select(ListingChecklist).where(
            ListingChecklist.property_id == property_id,
            ListingChecklist.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Checklist already exists for this property")

    # Validate sale method
    valid_methods = ("priced", "by_negotiation", "deadline", "auction")
    if payload.sale_method not in valid_methods:
        raise HTTPException(
            status_code=422,
            detail=f"sale_method must be one of: {', '.join(valid_methods)}",
        )

    # Create checklist
    cl = ListingChecklist(
        property_id=property_id,
        user_id=current_user.id,
        sale_method=payload.sale_method,
        current_phase=1,
    )
    db.add(cl)
    await db.flush()

    # Seed phases
    for phase_num, phase_name in PHASE_NAMES.items():
        phase = ChecklistPhase(
            checklist_id=cl.id,
            phase_number=phase_num,
            phase_name=phase_name,
        )
        db.add(phase)

    # Seed items from template
    template_items = get_template_items(payload.sale_method)
    for phase_num, item_texts in template_items.items():
        for idx, text in enumerate(item_texts):
            item = ChecklistItem(
                checklist_id=cl.id,
                phase_number=phase_num,
                item_text=text,
                sort_order=idx,
            )
            db.add(item)

    await db.flush()
    await db.refresh(cl)
    return _build_checklist_response(cl)


# ── PATCH update current_phase ───────────────────────────────────────────────


@checklists_router.patch(
    "/{checklist_id}/phase",
    response_model=ChecklistResponse,
)
async def update_checklist_phase(
    checklist_id: int,
    payload: PhaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually update the current phase of a checklist."""
    result = await db.execute(
        select(ListingChecklist).where(
            ListingChecklist.id == checklist_id,
            ListingChecklist.user_id == current_user.id,
        )
    )
    cl = result.scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")

    if payload.current_phase < 1 or payload.current_phase > 12:
        raise HTTPException(status_code=422, detail="current_phase must be between 1 and 12")

    cl.current_phase = payload.current_phase
    await db.flush()
    await db.refresh(cl)
    return _build_checklist_response(cl)


# ── DELETE checklist ─────────────────────────────────────────────────────────


@checklists_router.delete("/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(
    checklist_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a listing checklist and all its phases and items."""
    result = await db.execute(
        select(ListingChecklist).where(
            ListingChecklist.id == checklist_id,
            ListingChecklist.user_id == current_user.id,
        )
    )
    cl = result.scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")
    await db.delete(cl)
    await db.flush()


# ── PATCH update a checklist item ────────────────────────────────────────────


@items_router.patch("/{item_id}", response_model=ChecklistItemResponse)
async def update_checklist_item(
    item_id: int,
    payload: ChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a checklist item (mark complete, set due_date, note).

    When an item is marked complete, checks if all items in that phase
    are now complete — if so, marks the phase as complete and advances
    current_phase.
    """
    result = await db.execute(
        select(ChecklistItem).where(ChecklistItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    # Verify ownership
    cl_result = await db.execute(
        select(ListingChecklist).where(
            ListingChecklist.id == item.checklist_id,
            ListingChecklist.user_id == current_user.id,
        )
    )
    cl = cl_result.scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle completion timestamp
    if "is_complete" in update_data:
        if update_data["is_complete"] and not item.is_complete:
            update_data["completed_at"] = datetime.now(timezone.utc)
        elif not update_data["is_complete"]:
            update_data["completed_at"] = None

    for key, value in update_data.items():
        setattr(item, key, value)

    await db.flush()
    await db.refresh(item)

    # Auto-complete phase if all items in this phase are done
    if item.is_complete:
        phase_items_result = await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.checklist_id == cl.id,
                ChecklistItem.phase_number == item.phase_number,
            )
        )
        phase_items = phase_items_result.scalars().all()
        all_done = all(i.is_complete for i in phase_items)

        if all_done:
            # Mark the phase as complete
            phase_result = await db.execute(
                select(ChecklistPhase).where(
                    ChecklistPhase.checklist_id == cl.id,
                    ChecklistPhase.phase_number == item.phase_number,
                )
            )
            phase = phase_result.scalar_one_or_none()
            if phase and not phase.is_complete:
                phase.is_complete = True
                phase.completed_at = datetime.now(timezone.utc)

            # Advance current_phase if this was the current phase
            if cl.current_phase == item.phase_number and cl.current_phase < 12:
                cl.current_phase = item.phase_number + 1

            await db.flush()

    return item

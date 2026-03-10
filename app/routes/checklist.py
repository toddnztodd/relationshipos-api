"""Listing Checklist CRUD routes — nested and top-level."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Property, ListingChecklistItem
from app.schemas.checklist import ChecklistItemCreate, ChecklistItemUpdate, ChecklistItemResponse
from app.services.auth import get_current_user

# Nested router: /api/v1/properties/{property_id}/checklist
router = APIRouter(prefix="/properties", tags=["Listing Checklist"])

# Top-level router: /api/v1/checklist-items
top_router = APIRouter(prefix="/checklist-items", tags=["Listing Checklist"])


# ── Nested endpoints ──────────────────────────────────────────────────────────


@router.get("/{property_id}/checklist", response_model=list[ChecklistItemResponse])
async def list_checklist(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all checklist items for a property, ordered by sort_order."""
    prop = (await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(ListingChecklistItem).where(
            ListingChecklistItem.property_id == property_id,
            ListingChecklistItem.owner_id == current_user.id,
        ).order_by(ListingChecklistItem.sort_order, ListingChecklistItem.id)
    )
    return result.scalars().all()


@router.post("/{property_id}/checklist", response_model=list[ChecklistItemResponse], status_code=201)
async def create_checklist_items(
    property_id: int,
    payload: list[ChecklistItemCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create one or more checklist items for a property (accepts array)."""
    prop = (await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    items = []
    for item_data in payload:
        item = ListingChecklistItem(
            owner_id=current_user.id,
            property_id=property_id,
            phase=item_data.phase,
            step_name=item_data.step_name,
            is_completed=item_data.is_completed,
            due_date=item_data.due_date,
            notes=item_data.notes,
            sort_order=item_data.sort_order,
            sale_method=item_data.sale_method,
        )
        if item_data.is_completed:
            item.completed_at = datetime.now(timezone.utc)
        db.add(item)
        items.append(item)

    await db.flush()
    for item in items:
        await db.refresh(item)
    return items


@router.patch("/{property_id}/checklist/{item_id}", response_model=ChecklistItemResponse)
async def update_checklist_item(
    property_id: int,
    item_id: int,
    payload: ChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a checklist item (toggle complete, set due date, notes, etc.)."""
    result = await db.execute(
        select(ListingChecklistItem).where(
            ListingChecklistItem.id == item_id,
            ListingChecklistItem.property_id == property_id,
            ListingChecklistItem.owner_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "is_completed" in update_data:
        if update_data["is_completed"] and not item.is_completed:
            update_data["completed_at"] = datetime.now(timezone.utc)
        elif not update_data["is_completed"]:
            update_data["completed_at"] = None

    for key, value in update_data.items():
        setattr(item, key, value)

    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{property_id}/checklist/{item_id}", status_code=204)
async def delete_checklist_item(
    property_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a single checklist item."""
    result = await db.execute(
        select(ListingChecklistItem).where(
            ListingChecklistItem.id == item_id,
            ListingChecklistItem.property_id == property_id,
            ListingChecklistItem.owner_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    await db.delete(item)
    await db.flush()


@router.delete("/{property_id}/checklist", status_code=204)
async def clear_checklist(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all checklist items for a property."""
    prop = (await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(ListingChecklistItem).where(
            ListingChecklistItem.property_id == property_id,
            ListingChecklistItem.owner_id == current_user.id,
        )
    )
    for item in result.scalars().all():
        await db.delete(item)
    await db.flush()


# ── Top-level endpoints ──────────────────────────────────────────────────────


@top_router.patch("/{item_id}", response_model=ChecklistItemResponse)
async def update_checklist_item_toplevel(
    item_id: int,
    payload: ChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a checklist item by ID (top-level)."""
    result = await db.execute(
        select(ListingChecklistItem).where(
            ListingChecklistItem.id == item_id,
            ListingChecklistItem.owner_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "is_completed" in update_data:
        if update_data["is_completed"] and not item.is_completed:
            update_data["completed_at"] = datetime.now(timezone.utc)
        elif not update_data["is_completed"]:
            update_data["completed_at"] = None

    for key, value in update_data.items():
        setattr(item, key, value)

    await db.flush()
    await db.refresh(item)
    return item

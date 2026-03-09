"""Property CRUD routes with filtering."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Property
from app.schemas.property import PropertyCreate, PropertyUpdate, PropertyResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    payload: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new property record."""
    prop = Property(user_id=current_user.id, **payload.model_dump())
    db.add(prop)
    await db.flush()
    await db.refresh(prop)
    return prop


@router.get("/", response_model=list[PropertyResponse])
async def list_properties(
    suburb: Optional[str] = Query(None),
    bedrooms_min: Optional[int] = Query(None, ge=0),
    bedrooms_max: Optional[int] = Query(None, ge=0),
    has_pool: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search address or suburb"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List properties with optional filtering and pagination."""
    query = select(Property).where(Property.user_id == current_user.id)

    if suburb:
        query = query.where(Property.suburb.ilike(f"%{suburb}%"))
    if bedrooms_min is not None:
        query = query.where(Property.bedrooms >= bedrooms_min)
    if bedrooms_max is not None:
        query = query.where(Property.bedrooms <= bedrooms_max)
    if has_pool is not None:
        query = query.where(Property.has_pool == has_pool)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Property.address.ilike(pattern)) | (Property.suburb.ilike(pattern))
        )

    query = query.order_by(Property.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single property by ID."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    payload: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a property record."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(prop, key, value)

    await db.flush()
    await db.refresh(prop)
    return prop


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a property record."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    await db.delete(prop)
    await db.flush()

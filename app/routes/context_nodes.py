"""Routes for Context Nodes — CRUD, person/property attachment, and suggestions."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import (
    User, Person, Property,
    ContextNode, PersonContextNode, PropertyContextNode,
    ContextNodeSuggestion, ContextSuggestionStatus, ContextNodeType,
)
from app.schemas.context_node import (
    ContextNodeCreate, ContextNodeResponse, ContextNodeBrief,
    AttachContextNodeRequest,
    PersonContextNodesResponse, PropertyContextNodesResponse,
    ContextNodeSuggestionResponse, ContextNodeSuggestionUpdate,
)
from app.services.auth import get_current_user


# ── Routers ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/context-nodes", tags=["Context Nodes"])
person_router = APIRouter(prefix="/people", tags=["Context Nodes"])
property_router = APIRouter(prefix="/properties", tags=["Context Nodes"])
suggestion_router = APIRouter(prefix="/context-node-suggestions", tags=["Context Nodes"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_person(db: AsyncSession, person_id: int, user_id: int) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


async def _get_property(db: AsyncSession, property_id: int, user_id: int) -> Property:
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


async def _get_or_create_node(db: AsyncSession, req: AttachContextNodeRequest) -> ContextNode:
    """Get an existing node by ID, or create a new one from name+type."""
    if req.context_node_id:
        result = await db.execute(
            select(ContextNode).where(ContextNode.id == req.context_node_id)
        )
        node = result.scalar_one_or_none()
        if not node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context node not found")
        return node

    if not req.name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either context_node_id or name to create a new node.",
        )

    # Check for existing node with same name (case-insensitive)
    result = await db.execute(
        select(ContextNode).where(ContextNode.name.ilike(req.name.strip()))
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    node = ContextNode(name=req.name.strip(), type=req.type)
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


# ── Context Node CRUD ─────────────────────────────────────────────────────────

@router.get("/", response_model=list[ContextNodeResponse])
async def list_context_nodes(
    type: ContextNodeType | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all context nodes, optionally filtered by type."""
    query = select(ContextNode).order_by(ContextNode.name)
    if type:
        query = query.where(ContextNode.type == type)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=ContextNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_context_node(
    payload: ContextNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new context node."""
    # Check for duplicate name
    result = await db.execute(
        select(ContextNode).where(ContextNode.name.ilike(payload.name.strip()))
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Context node '{existing.name}' already exists (id={existing.id}).",
        )

    node = ContextNode(name=payload.name.strip(), type=payload.type)
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a context node (cascades to all links)."""
    result = await db.execute(select(ContextNode).where(ContextNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context node not found")
    await db.delete(node)


# ── Person Context Nodes ──────────────────────────────────────────────────────

@person_router.get("/{person_id}/context-nodes", response_model=PersonContextNodesResponse)
async def get_person_context_nodes(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all context nodes attached to a person."""
    await _get_person(db, person_id, current_user.id)

    result = await db.execute(
        select(PersonContextNode)
        .options(selectinload(PersonContextNode.context_node))
        .where(PersonContextNode.person_id == person_id)
    )
    links = result.scalars().all()
    nodes = [
        ContextNodeBrief(id=link.context_node.id, name=link.context_node.name, type=link.context_node.type)
        for link in links if link.context_node
    ]
    return PersonContextNodesResponse(person_id=person_id, context_nodes=nodes)


@person_router.post(
    "/{person_id}/context-nodes",
    response_model=ContextNodeBrief,
    status_code=status.HTTP_201_CREATED,
)
async def attach_context_node_to_person(
    person_id: int,
    payload: AttachContextNodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach a context node to a person (create node if needed)."""
    await _get_person(db, person_id, current_user.id)
    node = await _get_or_create_node(db, payload)

    # Check if already linked
    result = await db.execute(
        select(PersonContextNode).where(
            PersonContextNode.context_node_id == node.id,
            PersonContextNode.person_id == person_id,
        )
    )
    if result.scalar_one_or_none():
        return ContextNodeBrief(id=node.id, name=node.name, type=node.type)

    link = PersonContextNode(context_node_id=node.id, person_id=person_id)
    db.add(link)
    await db.flush()
    return ContextNodeBrief(id=node.id, name=node.name, type=node.type)


@person_router.delete("/{person_id}/context-nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_context_node_from_person(
    person_id: int,
    node_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detach a context node from a person."""
    await _get_person(db, person_id, current_user.id)
    result = await db.execute(
        select(PersonContextNode).where(
            PersonContextNode.context_node_id == node_id,
            PersonContextNode.person_id == person_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    await db.delete(link)


# ── Property Context Nodes ────────────────────────────────────────────────────

@property_router.get("/{property_id}/context-nodes", response_model=PropertyContextNodesResponse)
async def get_property_context_nodes(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all context nodes attached to a property."""
    await _get_property(db, property_id, current_user.id)

    result = await db.execute(
        select(PropertyContextNode)
        .options(selectinload(PropertyContextNode.context_node))
        .where(PropertyContextNode.property_id == property_id)
    )
    links = result.scalars().all()
    nodes = [
        ContextNodeBrief(id=link.context_node.id, name=link.context_node.name, type=link.context_node.type)
        for link in links if link.context_node
    ]
    return PropertyContextNodesResponse(property_id=property_id, context_nodes=nodes)


@property_router.post(
    "/{property_id}/context-nodes",
    response_model=ContextNodeBrief,
    status_code=status.HTTP_201_CREATED,
)
async def attach_context_node_to_property(
    property_id: int,
    payload: AttachContextNodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach a context node to a property (create node if needed)."""
    await _get_property(db, property_id, current_user.id)
    node = await _get_or_create_node(db, payload)

    result = await db.execute(
        select(PropertyContextNode).where(
            PropertyContextNode.context_node_id == node.id,
            PropertyContextNode.property_id == property_id,
        )
    )
    if result.scalar_one_or_none():
        return ContextNodeBrief(id=node.id, name=node.name, type=node.type)

    link = PropertyContextNode(context_node_id=node.id, property_id=property_id)
    db.add(link)
    await db.flush()
    return ContextNodeBrief(id=node.id, name=node.name, type=node.type)


@property_router.delete("/{property_id}/context-nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_context_node_from_property(
    property_id: int,
    node_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detach a context node from a property."""
    await _get_property(db, property_id, current_user.id)
    result = await db.execute(
        select(PropertyContextNode).where(
            PropertyContextNode.context_node_id == node_id,
            PropertyContextNode.property_id == property_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    await db.delete(link)


# ── Context Node Suggestions ─────────────────────────────────────────────────

@person_router.get("/{person_id}/context-node-suggestions", response_model=list[ContextNodeSuggestionResponse])
async def get_person_context_node_suggestions(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get pending context node suggestions for a person."""
    await _get_person(db, person_id, current_user.id)

    result = await db.execute(
        select(ContextNodeSuggestion).where(
            ContextNodeSuggestion.person_id == person_id,
            ContextNodeSuggestion.user_id == current_user.id,
            ContextNodeSuggestion.status == ContextSuggestionStatus.suggested,
        ).order_by(ContextNodeSuggestion.created_at.desc())
    )
    return result.scalars().all()


@suggestion_router.patch("/{suggestion_id}", response_model=ContextNodeSuggestionResponse)
async def update_context_node_suggestion(
    suggestion_id: int,
    payload: ContextNodeSuggestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept or dismiss a context node suggestion.

    Accepting creates the context_node (if new) and links it to the person.
    """
    result = await db.execute(
        select(ContextNodeSuggestion).where(
            ContextNodeSuggestion.id == suggestion_id,
            ContextNodeSuggestion.user_id == current_user.id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")

    new_status = ContextSuggestionStatus(payload.status)
    suggestion.status = new_status

    if new_status == ContextSuggestionStatus.accepted and suggestion.person_id:
        # Create or find the context node
        node_result = await db.execute(
            select(ContextNode).where(ContextNode.name.ilike(suggestion.suggested_name.strip()))
        )
        node = node_result.scalar_one_or_none()
        if not node:
            node = ContextNode(name=suggestion.suggested_name.strip(), type=suggestion.suggested_type)
            db.add(node)
            await db.flush()
            await db.refresh(node)

        # Link to person if not already linked
        link_result = await db.execute(
            select(PersonContextNode).where(
                PersonContextNode.context_node_id == node.id,
                PersonContextNode.person_id == suggestion.person_id,
            )
        )
        if not link_result.scalar_one_or_none():
            db.add(PersonContextNode(context_node_id=node.id, person_id=suggestion.person_id))

    await db.flush()
    await db.refresh(suggestion)
    return suggestion

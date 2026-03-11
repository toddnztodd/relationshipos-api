"""Property Intelligence — match and voice-parse endpoints."""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Property
from app.schemas.property import (
    PropertyMatchRequest,
    PropertyMatchResponse,
    PropertyParseVoiceRequest,
    PropertyParseVoiceResponse,
    PropertyResponse,
)
from app.services.auth import get_current_user
from app.services.parse_property_voice import parse_property_voice

router = APIRouter(prefix="/properties", tags=["Property Intelligence"])


# ── Address normalisation ─────────────────────────────────────────────────────

_STRIP_WORDS = {"street", "st", "road", "rd", "avenue", "ave", "drive", "dr",
                "place", "pl", "terrace", "tce", "crescent", "cres", "lane", "ln",
                "way", "close", "cl", "court", "ct", "boulevard", "blvd"}


def _normalise_address(address: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy matching."""
    addr = address.lower().strip()
    addr = re.sub(r"[,.\-/\\#]", " ", addr)
    addr = re.sub(r"\s+", " ", addr).strip()
    return addr


def _address_tokens(normalised: str) -> set:
    return set(normalised.split())


def _match_confidence(query_norm: str, candidate_norm: str) -> str:
    """Return 'exact', 'likely', or 'none'."""
    if query_norm == candidate_norm:
        return "exact"

    q_tokens = _address_tokens(query_norm)
    c_tokens = _address_tokens(candidate_norm)

    # Remove common street-type words for comparison
    q_core = q_tokens - _STRIP_WORDS
    c_core = c_tokens - _STRIP_WORDS

    if q_core and c_core and q_core == c_core:
        return "exact"

    # Check overlap ratio
    if q_core and c_core:
        overlap = len(q_core & c_core) / max(len(q_core), len(c_core))
        if overlap >= 0.7:
            return "likely"

    return "none"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/match", response_model=PropertyMatchResponse)
async def match_property(
    payload: PropertyMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Find an existing property by normalised address matching.

    Returns the best match with a confidence level: exact, likely, or none.
    """
    query_norm = _normalise_address(payload.address)
    if not query_norm:
        return PropertyMatchResponse(match=None, confidence="none")

    # Get all user properties (typically < 1000)
    result = await db.execute(
        select(Property).where(Property.user_id == current_user.id)
    )
    properties = result.scalars().all()

    best_match = None
    best_confidence = "none"

    for prop in properties:
        candidate_norm = _normalise_address(prop.address)
        confidence = _match_confidence(query_norm, candidate_norm)

        if confidence == "exact":
            best_match = prop
            best_confidence = "exact"
            break
        elif confidence == "likely" and best_confidence != "exact":
            best_match = prop
            best_confidence = "likely"

    if best_match:
        return PropertyMatchResponse(
            match=PropertyResponse.model_validate(best_match),
            confidence=best_confidence,
        )
    return PropertyMatchResponse(match=None, confidence="none")


@router.post("/parse-voice", response_model=PropertyParseVoiceResponse)
async def parse_property_voice_endpoint(
    payload: PropertyParseVoiceRequest,
    current_user=Depends(get_current_user),
):
    """Extract structured property fields from a voice transcription.

    Accepts a free-form transcription and returns structured property data
    ready to pre-fill a property form. No property is created — parsing only.
    """
    if not payload.transcription or not payload.transcription.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="transcription must not be empty",
        )
    try:
        result = await parse_property_voice(payload.transcription.strip())
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    return result

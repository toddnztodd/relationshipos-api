"""Cadence tracking and drift detection service."""

from datetime import datetime, timezone

from app.models.models import TierEnum, CadenceStatus

# Cadence windows in days
CADENCE_WINDOWS = {
    TierEnum.A: 30,
    TierEnum.B: 60,
    TierEnum.C: 90,
}

AMBER_THRESHOLD_DAYS = 7  # within 7 days of deadline → amber


def get_cadence_window(tier: TierEnum) -> int:
    """Return the cadence window in days for a given tier."""
    return CADENCE_WINDOWS.get(tier, 90)


def compute_cadence_status(
    tier: TierEnum,
    last_meaningful_date: datetime | None,
    now: datetime | None = None,
) -> tuple[CadenceStatus, int | None]:
    """
    Compute cadence status for a person.

    Returns:
        (status, days_since_last_meaningful)
        status: green | amber | red
        days_since_last_meaningful: None if no meaningful interaction recorded
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window = get_cadence_window(tier)

    if last_meaningful_date is None:
        # No meaningful interaction ever recorded → red
        return CadenceStatus.red, None

    # Ensure timezone-aware comparison
    if last_meaningful_date.tzinfo is None:
        last_meaningful_date = last_meaningful_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    days_since = (now - last_meaningful_date).days

    if days_since > window:
        return CadenceStatus.red, days_since
    elif days_since >= (window - AMBER_THRESHOLD_DAYS):
        return CadenceStatus.amber, days_since
    else:
        return CadenceStatus.green, days_since


def days_until_deadline(
    tier: TierEnum,
    last_meaningful_date: datetime | None,
    now: datetime | None = None,
) -> int | None:
    """Return days until the cadence deadline. Negative means overdue."""
    if last_meaningful_date is None:
        return None
    if now is None:
        now = datetime.now(timezone.utc)

    if last_meaningful_date.tzinfo is None:
        last_meaningful_date = last_meaningful_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    window = get_cadence_window(tier)
    days_since = (now - last_meaningful_date).days
    return window - days_since

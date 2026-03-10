"""Per-user TTL cache for the dashboard summary endpoint.

Cache stores the full computed DashboardResponse dict per user_id.
Entries expire after CACHE_TTL_SECONDS (default 300 = 5 minutes).
Any mutation (activity logged, person updated) invalidates the cache
for the affected user_id via `invalidate(user_id)`.
"""

import time
from typing import Any

CACHE_TTL_SECONDS = 300  # 5 minutes

# Simple dict-based cache: {user_id: (timestamp, data)}
_cache: dict[int, tuple[float, Any]] = {}


def get(user_id: int) -> Any | None:
    """Return cached dashboard data if it exists and hasn't expired."""
    entry = _cache.get(user_id)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        # Expired — remove and return None
        _cache.pop(user_id, None)
        return None
    return data


def put(user_id: int, data: Any) -> None:
    """Store dashboard data in the cache."""
    _cache[user_id] = (time.time(), data)


def invalidate(user_id: int) -> None:
    """Invalidate the cached dashboard data for a specific user."""
    _cache.pop(user_id, None)


def clear_all() -> None:
    """Clear the entire cache (for testing or admin use)."""
    _cache.clear()

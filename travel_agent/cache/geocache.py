"""Async TTL caches for Nominatim geocoding and Overpass API results."""

from __future__ import annotations

from asyncio import Lock
from dataclasses import dataclass, field
from time import monotonic
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl: float

    @property
    def is_expired(self) -> bool:
        return monotonic() - self.created_at > self.ttl


class TTLCache:
    """Thread-safe async TTL cache using asyncio.Lock."""

    def __init__(self, ttl: float = 86400.0, max_size: int = 1000):
        self._ttl = ttl
        self._max_size = max_size
        self._store: dict[str, CacheEntry] = {}
        self._lock = Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._store[key]
                return None
            return entry.value

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            # Evict oldest entry if at capacity
            if len(self._store) >= self._max_size and key not in self._store:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[key] = CacheEntry(
                value=value,
                created_at=monotonic(),
                ttl=self._ttl,
            )

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear_expired(self) -> int:
        async with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired]
            for k in expired:
                del self._store[k]
            return len(expired)


# Module-level singletons (24h for geocoding, 1h for Overpass place data)
geocode_cache = TTLCache(ttl=86400.0)
overpass_cache = TTLCache(ttl=3600.0)

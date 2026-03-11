"""Unit tests for travel_agent/cache/geocache.py and tools sync cache."""

import asyncio
import time

import pytest

from travel_agent.cache.geocache import TTLCache


class TestTTLCache:
    @pytest.fixture
    def cache(self):
        return TTLCache(ttl=60.0, max_size=10)

    @pytest.mark.asyncio
    async def test_miss_then_hit(self, cache):
        assert await cache.get("key1") is None
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, cache):
        await cache.set("a", 1)
        await cache.set("b", 2)
        assert await cache.get("a") == 1
        assert await cache.get("b") == 2

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        short_cache = TTLCache(ttl=0.05, max_size=100)
        await short_cache.set("x", "hello")
        assert await short_cache.get("x") == "hello"
        await asyncio.sleep(0.1)
        assert await short_cache.get("x") is None

    @pytest.mark.asyncio
    async def test_overwrite_resets_ttl(self):
        short_cache = TTLCache(ttl=0.1, max_size=100)
        await short_cache.set("x", "v1")
        await asyncio.sleep(0.06)
        await short_cache.set("x", "v2")  # reset TTL
        await asyncio.sleep(0.06)
        assert await short_cache.get("x") == "v2"  # still alive

    @pytest.mark.asyncio
    async def test_invalidate_removes_entry(self, cache):
        await cache.set("k", "v")
        await cache.invalidate("k")
        assert await cache.get("k") is None

    @pytest.mark.asyncio
    async def test_invalidate_missing_key_no_error(self, cache):
        await cache.invalidate("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_max_size_evicts_oldest(self):
        small_cache = TTLCache(ttl=3600.0, max_size=3)
        await small_cache.set("a", 1)
        await small_cache.set("b", 2)
        await small_cache.set("c", 3)
        # Adding a 4th entry should evict the oldest ("a")
        await small_cache.set("d", 4)
        assert await small_cache.get("a") is None
        assert await small_cache.get("d") == 4

    @pytest.mark.asyncio
    async def test_clear_expired_returns_count(self):
        short_cache = TTLCache(ttl=0.05, max_size=100)
        await short_cache.set("x", 1)
        await short_cache.set("y", 2)
        await asyncio.sleep(0.1)
        await short_cache.set("z", 3)  # fresh entry

        count = await short_cache.clear_expired()
        assert count == 2
        assert await short_cache.get("z") == 3

    @pytest.mark.asyncio
    async def test_concurrent_writes_safe(self):
        cache = TTLCache(ttl=60.0, max_size=100)

        async def write(i):
            await cache.set(f"key{i}", i)

        await asyncio.gather(*[write(i) for i in range(50)])
        # All 50 entries should be present
        results = await asyncio.gather(*[cache.get(f"key{i}") for i in range(50)])
        assert all(r is not None for r in results)


class TestSyncTTLCache:
    """Tests for the synchronous _SyncTTLCache used in tools.py."""

    def test_basic_set_get(self):
        from travel_agent.tools import _SyncTTLCache

        cache = _SyncTTLCache(ttl=60.0)
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_miss_returns_none(self):
        from travel_agent.tools import _SyncTTLCache

        cache = _SyncTTLCache(ttl=60.0)
        assert cache.get("missing") is None

    def test_expiry(self):
        from travel_agent.tools import _SyncTTLCache

        cache = _SyncTTLCache(ttl=0.05)
        cache.set("k", "v")
        time.sleep(0.1)
        assert cache.get("k") is None

    def test_max_size_evicts_oldest(self):
        from travel_agent.tools import _SyncTTLCache

        cache = _SyncTTLCache(ttl=3600.0, max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("c") == 3

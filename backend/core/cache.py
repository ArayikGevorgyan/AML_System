"""
In-Memory Cache
================
Thread-safe in-memory caching with TTL support for the AML backend.
Designed for caching expensive DB queries (e.g. dashboard KPIs, sanctions counts).

Components:
  - InMemoryCache: Core cache class with get/set/TTL/stats.
  - cached:        Function decorator for automatic cache wrapping.

Usage:
    from core.cache import InMemoryCache, cached

    cache = InMemoryCache(default_ttl=300)

    # Direct usage
    cache.set("dashboard_kpis", data, ttl_seconds=60)
    result = cache.get("dashboard_kpis")

    # Decorator usage
    @cached(ttl=120, key_prefix="risk_score")
    def get_risk_score(customer_id: int) -> float:
        ...
"""

import threading
import time
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Sentinel for cache miss
_MISSING = object()


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

class _CacheEntry:
    """
    Internal representation of a single cached item.

    Attributes:
        value:      The cached value.
        expires_at: Monotonic timestamp when this entry expires (None = never).
        created_at: Real datetime when this entry was created.
        hit_count:  Number of times this entry has been read.
    """

    __slots__ = ("value", "expires_at", "created_at", "hit_count")

    def __init__(self, value: Any, ttl_seconds: Optional[float]) -> None:
        self.value = value
        self.created_at = datetime.now(timezone.utc)
        self.hit_count = 0
        if ttl_seconds is not None and ttl_seconds > 0:
            self.expires_at = time.monotonic() + ttl_seconds
        else:
            self.expires_at = None

    def is_expired(self) -> bool:
        """Return True if this entry has passed its TTL."""
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at

    def ttl_remaining(self) -> Optional[float]:
        """Return seconds remaining until expiry, or None if no TTL."""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - time.monotonic()
        return max(0.0, remaining)


# ---------------------------------------------------------------------------
# InMemoryCache
# ---------------------------------------------------------------------------

class InMemoryCache:
    """
    Thread-safe in-memory cache with per-entry TTL support.

    Attributes:
        default_ttl:  Default TTL in seconds for new entries (None = never expire).
        max_size:     Maximum number of entries (oldest entries evicted when full).
        _store:       Internal dict of key → _CacheEntry.
        _lock:        Threading lock for concurrent access.
        _hits:        Total cache hit count.
        _misses:      Total cache miss count.
    """

    def __init__(
        self,
        default_ttl: Optional[float] = 300,
        max_size: int = 1000,
    ) -> None:
        """
        Initialize the cache.

        Args:
            default_ttl: Default TTL in seconds (default 300s = 5 min).
                         Set to None for no expiry by default.
            max_size:    Maximum number of cached entries.
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._store: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._total_sets = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache.

        Returns None on cache miss or if the entry has expired.

        Args:
            key: Cache key.

        Returns:
            Cached value or None.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired():
                del self._store[key]
                self._misses += 1
                return None
            entry.hit_count += 1
            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """
        Store a value in the cache with an optional TTL.

        If the cache is at max_size, the oldest entry (by creation time) is evicted.

        Args:
            key:         Cache key.
            value:       Value to cache.
            ttl_seconds: Seconds until expiry. Uses default_ttl if None.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        entry = _CacheEntry(value, ttl)

        with self._lock:
            # Evict oldest if at capacity
            if key not in self._store and len(self._store) >= self.max_size:
                oldest_key = min(
                    self._store.keys(),
                    key=lambda k: self._store[k].created_at,
                )
                del self._store[oldest_key]
                logger.debug("Cache evicted oldest entry: %s", oldest_key)

            self._store[key] = entry
            self._total_sets += 1

    def delete(self, key: str) -> bool:
        """
        Remove a specific key from the cache.

        Args:
            key: The key to remove.

        Returns:
            True if the key existed and was deleted, False otherwise.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                logger.debug("Cache deleted key: %s", key)
                return True
            return False

    def clear(self) -> int:
        """
        Remove all entries from the cache.

        Returns:
            Number of entries cleared.
        """
        with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.info("Cache cleared: %d entries removed.", count)
            return count

    def get_or_set(
        self,
        key: str,
        fn: Callable[[], Any],
        ttl_seconds: Optional[float] = None,
    ) -> Any:
        """
        Return cached value if present; otherwise call fn(), cache and return result.

        Args:
            key:         Cache key.
            fn:          Zero-argument callable to produce the value on miss.
            ttl_seconds: TTL for the new entry.

        Returns:
            Cached or freshly computed value.
        """
        cached_val = self.get(key)
        if cached_val is not None:
            return cached_val

        value = fn()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def invalidate_pattern(self, prefix: str) -> int:
        """
        Delete all cache keys that start with the given prefix.

        Useful for invalidating related entries (e.g. "customer:42:*").

        Args:
            prefix: Key prefix to match.

        Returns:
            Number of keys removed.
        """
        with self._lock:
            matching = [k for k in self._store if k.startswith(prefix)]
            for key in matching:
                del self._store[key]
            if matching:
                logger.debug("Cache invalidated %d keys with prefix '%s'.", len(matching), prefix)
            return len(matching)

    def cleanup_expired(self) -> int:
        """
        Scan the cache and remove all expired entries.

        Returns:
            Number of expired entries removed.
        """
        with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired()]
            for key in expired:
                del self._store[key]
            if expired:
                logger.debug("Cache cleanup: removed %d expired entries.", len(expired))
            return len(expired)

    def stats(self) -> Dict[str, Any]:
        """
        Return cache statistics.

        Returns:
            Dict containing:
                - size: Current number of entries
                - max_size: Maximum capacity
                - hits: Total hit count
                - misses: Total miss count
                - hit_rate: Float in [0, 1]
                - total_sets: Total number of set() calls
                - expired_entries: Entries currently past their TTL
        """
        with self._lock:
            expired_count = sum(1 for v in self._store.values() if v.is_expired())
            total_requests = self._hits + self._misses
            hit_rate = round(self._hits / total_requests, 4) if total_requests > 0 else 0.0

            return {
                "size": len(self._store),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "total_sets": self._total_sets,
                "expired_entries": expired_count,
                "default_ttl_seconds": self.default_ttl,
            }

    def keys(self) -> list:
        """Return list of all current cache keys (excluding expired)."""
        with self._lock:
            return [k for k, v in self._store.items() if not v.is_expired()]

    def __contains__(self, key: str) -> bool:
        """Support 'key in cache' syntax."""
        val = self.get(key)
        return val is not None

    def __len__(self) -> int:
        """Return number of (potentially expired) entries."""
        with self._lock:
            return len(self._store)

    def __repr__(self) -> str:
        return (
            f"InMemoryCache(size={len(self._store)}, "
            f"max_size={self.max_size}, "
            f"default_ttl={self.default_ttl}s)"
        )


# ---------------------------------------------------------------------------
# Global shared instance
# ---------------------------------------------------------------------------

# Shared cache instance with 5-minute default TTL
_cache = InMemoryCache(default_ttl=300, max_size=500)


def get_cache() -> InMemoryCache:
    """Return the global shared cache instance."""
    return _cache


# ---------------------------------------------------------------------------
# cached decorator
# ---------------------------------------------------------------------------

def cached(
    ttl: Optional[float] = 300,
    key_prefix: Optional[str] = None,
    cache_instance: Optional[InMemoryCache] = None,
):
    """
    Decorator that caches a function's return value.

    The cache key is built from key_prefix + function name + args/kwargs.
    Only positional arguments and keyword arguments with simple string/int/float
    representations are used in the key.

    Args:
        ttl:            TTL in seconds for cached entries (default 300).
        key_prefix:     Optional prefix for cache keys.
        cache_instance: Cache to use (defaults to global shared cache).

    Usage:
        @cached(ttl=60, key_prefix="dashboard")
        def get_kpi_data(db_url: str) -> dict:
            ...

        @cached(ttl=300)
        def expensive_query(customer_id: int, days: int) -> list:
            ...
    """
    cache = cache_instance or _cache

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and args
            prefix = key_prefix or func.__module__ + "." + func.__name__

            # Only include args that are safely hashable/stringable
            safe_args = []
            for arg in args:
                if isinstance(arg, (int, float, str, bool, type(None))):
                    safe_args.append(str(arg))
                else:
                    safe_args.append(f"obj_{type(arg).__name__}")

            safe_kwargs = []
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (int, float, str, bool, type(None))):
                    safe_kwargs.append(f"{k}={v}")
                else:
                    safe_kwargs.append(f"{k}=obj")

            key_parts = [prefix] + safe_args + safe_kwargs
            cache_key = ":".join(key_parts)

            result = cache.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, ttl_seconds=ttl)
            return result

        wrapper._cache_key_prefix = key_prefix or func.__qualname__
        wrapper._cache_instance = cache

        def invalidate(*args, **kwargs):
            """Invalidate cache for this function (or a specific call signature)."""
            prefix = key_prefix or func.__module__ + "." + func.__name__
            cache.invalidate_pattern(prefix)

        wrapper.invalidate = invalidate
        return wrapper

    return decorator

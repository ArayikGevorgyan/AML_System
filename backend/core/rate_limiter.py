"""
Rate Limiter
==============
In-memory rate limiting for the AML backend API.
Uses a sliding window approach per client key (IP or user ID).

Components:
  - RateLimiter:         Core in-memory limiter class.
  - RateLimitMiddleware: FastAPI ASGI middleware using RateLimiter.
  - rate_limit:          Decorator for per-endpoint rate limiting.

Usage:
    # As middleware (app-wide)
    from core.rate_limiter import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    # As decorator (per endpoint)
    from core.rate_limiter import rate_limit

    @router.get("/sensitive")
    @rate_limit(requests_per_minute=10)
    def sensitive_endpoint(request: Request):
        ...
"""

import threading
import time
import logging
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Any, Optional, Callable, Deque

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    In-memory sliding window rate limiter.

    Tracks request timestamps per key (e.g. client IP or user ID) using
    a deque. Thread-safe via a threading.Lock.

    Attributes:
        requests_per_minute: Maximum allowed requests per 60-second window.
        _store:              Dict[key → deque of timestamps].
        _lock:               Threading lock for thread safety.
    """

    def __init__(self, requests_per_minute: int = 60) -> None:
        """
        Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute per key.
        """
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self._store: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _clean_window(self, key: str) -> None:
        """
        Remove timestamps outside the current sliding window for a key.
        Must be called with lock held.

        Args:
            key: The rate limit key.
        """
        if key not in self._store:
            return
        cutoff = time.monotonic() - self.window_seconds
        dq = self._store[key]
        while dq and dq[0] < cutoff:
            dq.popleft()

    def is_allowed(self, key: str) -> bool:
        """
        Check whether a request from key is allowed and record it if so.

        This is the primary method called per request.

        Args:
            key: Client identifier (e.g. "192.168.1.1" or "user:42").

        Returns:
            True if the request is allowed, False if rate limit exceeded.
        """
        with self._lock:
            if key not in self._store:
                self._store[key] = deque()

            self._clean_window(key)

            if len(self._store[key]) >= self.requests_per_minute:
                logger.warning("Rate limit exceeded for key: %s", key)
                return False

            self._store[key].append(time.monotonic())
            return True

    def get_remaining(self, key: str) -> int:
        """
        Return the number of remaining requests allowed in the current window.

        Args:
            key: Client identifier.

        Returns:
            Number of remaining requests (0 if rate limited).
        """
        with self._lock:
            if key not in self._store:
                return self.requests_per_minute
            self._clean_window(key)
            used = len(self._store[key])
            return max(0, self.requests_per_minute - used)

    def reset(self, key: str) -> None:
        """
        Clear all request records for a given key.

        Useful for testing or administrative override.

        Args:
            key: The key to reset.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                logger.debug("Rate limiter reset for key: %s", key)

    def cleanup_expired(self) -> int:
        """
        Remove all keys that have no recent requests in the current window.

        Call periodically to prevent unbounded memory growth.

        Returns:
            Number of keys removed.
        """
        with self._lock:
            expired_keys = []
            for key in list(self._store.keys()):
                self._clean_window(key)
                if not self._store[key]:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug("Rate limiter cleanup: removed %d expired keys.", len(expired_keys))

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Return current rate limiter statistics.

        Returns:
            Dict with total tracked keys, requests_per_minute setting,
            and per-key counts.
        """
        with self._lock:
            return {
                "total_tracked_keys": len(self._store),
                "requests_per_minute": self.requests_per_minute,
                "window_seconds": self.window_seconds,
                "current_counts": {
                    key: len(dq)
                    for key, dq in self._store.items()
                },
            }

    def __repr__(self) -> str:
        return f"RateLimiter(requests_per_minute={self.requests_per_minute})"


# ---------------------------------------------------------------------------
# Default shared instance
# ---------------------------------------------------------------------------

# Shared instance — used by middleware and decorator by default
_default_limiter = RateLimiter(requests_per_minute=120)


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette ASGI middleware that applies rate limiting to all routes.

    Identifies clients by their IP address (from X-Forwarded-For or client.host).
    On rate limit breach, returns HTTP 429 with a Retry-After header.

    Usage:
        app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        exclude_paths: Optional[list] = None,
    ) -> None:
        """
        Initialize the middleware.

        Args:
            app:                 The ASGI application.
            requests_per_minute: Per-IP request limit.
            exclude_paths:       List of path prefixes to exclude from limiting.
        """
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute=requests_per_minute)
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Intercept each request to check the rate limit.

        Args:
            request:   The incoming HTTP request.
            call_next: The next middleware/handler in the chain.

        Returns:
            HTTP response, or 429 if rate limit exceeded.
        """
        path = request.url.path

        # Skip excluded paths
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return await call_next(request)

        # Determine client key
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        if not self.limiter.is_allowed(client_ip):
            remaining = self.limiter.get_remaining(client_ip)
            return Response(
                content='{"detail": "Rate limit exceeded. Try again in 60 seconds."}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.limiter.requests_per_minute),
                    "X-RateLimit-Remaining": str(remaining),
                },
            )

        response = await call_next(request)

        # Attach rate limit headers to all responses
        remaining = self.limiter.get_remaining(client_ip)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


# ---------------------------------------------------------------------------
# rate_limit decorator
# ---------------------------------------------------------------------------

def rate_limit(
    requests_per_minute: int = 30,
    key_func: Optional[Callable] = None,
    limiter: Optional[RateLimiter] = None,
):
    """
    Decorator factory to apply per-endpoint rate limiting.

    The decorated endpoint must accept a `request: Request` parameter.

    Args:
        requests_per_minute: Request limit for this endpoint.
        key_func:            Optional function to extract key from request.
                             Default: uses client IP.
        limiter:             Optional RateLimiter instance to use.
                             Default: creates a new one per endpoint.

    Usage:
        @router.get("/export")
        @rate_limit(requests_per_minute=5)
        def export_data(request: Request, ...):
            ...
    """
    _limiter = limiter or RateLimiter(requests_per_minute=requests_per_minute)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is not None:
                if key_func:
                    key = key_func(request)
                else:
                    forwarded = request.headers.get("X-Forwarded-For")
                    key = forwarded.split(",")[0].strip() if forwarded else (
                        request.client.host if request.client else "unknown"
                    )

                if not _limiter.is_allowed(key):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded: {requests_per_minute} req/min.",
                        headers={"Retry-After": "60"},
                    )

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is not None:
                if key_func:
                    key = key_func(request)
                else:
                    forwarded = request.headers.get("X-Forwarded-For")
                    key = forwarded.split(",")[0].strip() if forwarded else (
                        request.client.host if request.client else "unknown"
                    )

                if not _limiter.is_allowed(key):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded: {requests_per_minute} req/min.",
                        headers={"Retry-After": "60"},
                    )

            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator

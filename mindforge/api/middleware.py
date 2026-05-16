"""
FastAPI middleware stack for MindForge API.

Middleware applied (in stack order, outermost first):
1. Request size limiter — rejects oversized request bodies early.
2. Request ID propagation — injects ``X-Request-ID`` into every request.
3. CORS — configurable allowed origins.
4. Rate limiter (in-memory token bucket) — simple protection for auth
   endpoints; production deployments should front with a proper WAF/gateway.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request size limiter
# ---------------------------------------------------------------------------


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject any request body larger than ``max_bytes``."""

    def __init__(self, app: ASGIApp, max_bytes: int = 20 * 1024 * 1024) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "detail": f"Żądanie jest zbyt duże (max {self._max_bytes} B)."
                },
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique ``X-Request-ID`` to every request and response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Simple in-process token-bucket rate limiter
# ---------------------------------------------------------------------------


class _Bucket:
    """Mutable token-bucket state for a single key."""

    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens: float = capacity
        self.last_refill: float = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter keyed by client IP.

    Parameters
    ----------
    rate_per_minute:
        Maximum number of requests per minute for each IP.
    burst:
        Maximum burst size (default equals ``rate_per_minute``).
    path_prefix:
        Only apply rate limiting to paths starting with this prefix.
        Set to ``""`` to apply globally.
    """

    def __init__(
        self,
        app: ASGIApp,
        rate_per_minute: int = 60,
        burst: int | None = None,
        path_prefix: str = "/api/auth",
    ) -> None:
        super().__init__(app)
        self._rate = rate_per_minute / 60.0  # tokens per second
        self._capacity = float(burst if burst is not None else rate_per_minute)
        self._path_prefix = path_prefix
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(self._capacity))
        self._lock = asyncio.Lock()

    def _client_key(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if self._path_prefix and not request.url.path.startswith(self._path_prefix):
            return await call_next(request)

        key = self._client_key(request)

        async with self._lock:
            bucket = self._buckets[key]
            now = time.monotonic()
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._rate)
            bucket.last_refill = now

            if bucket.tokens < 1:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Zbyt wiele żądań. Spróbuj ponownie za chwilę."},
                    headers={"Retry-After": "60"},
                )
            bucket.tokens -= 1

        return await call_next(request)


# ---------------------------------------------------------------------------
# Helper — register all middleware on the FastAPI app
# ---------------------------------------------------------------------------


def add_middleware(
    app,  # FastAPI instance
    *,
    cors_origins: list[str] | None = None,
    max_request_bytes: int = 20 * 1024 * 1024,
    auth_rate_per_minute: int = 20,
) -> None:
    """Attach all MindForge middleware to *app* in the correct order."""

    # CORSMiddleware — must be added LAST (outermost in Starlette's middleware stack
    # is added first via add_middleware, but they are applied outer-to-inner).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:4200"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiter on auth endpoints
    app.add_middleware(
        RateLimitMiddleware,
        rate_per_minute=auth_rate_per_minute,
        path_prefix="/api/auth",
    )

    # Request ID
    app.add_middleware(RequestIDMiddleware)

    # Body size guard
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=max_request_bytes)

"""ASGI rate-limit middleware (Redis-backed fixed window with memory fallback).

Each client (IP by default, user id when the request context already resolved
one) may make at most ``max_requests`` calls per ``window_seconds``.  Exceeding
the limit returns 429 without touching the application.

Backend: a Redis fixed-window counter (``INCR`` + ``EXPIRE``) so the limit is
shared correctly across multiple API replicas/workers.  If Redis is
unreachable at request time the middleware falls back to an in-process
sliding-window counter so a broker outage degrades (per-process limits) rather
than fails open or crashes the request.
"""
import threading
import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.logging import get_logger
from app.middleware.request_context import current_org_id, current_user

logger = get_logger("rate_limit")

DEFAULT_MAX_REQUESTS = 600
DEFAULT_WINDOW_SECONDS = 60

_REDIS_NOTE = "rate limit exceeded client=%s"


def _make_redis_client():
    """Lazily build a shared Redis client from REDIS_URL (None if unset)."""
    try:
        import redis
    except ImportError:
        return None
    url = getattr(settings, "REDIS_URL", None)
    if not url:
        return None
    try:
        return redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    except Exception:
        return None


class RateLimitExceeded(Exception):
    """Raised internally when the client exceeded its quota."""


class RateLimitMiddleware:
    """Per-client limiter returning 429 responses (Redis + in-memory fallback)."""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: defaultdict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        self._redis = None
        self._redis_init = False

    # -- backend selection -------------------------------------------------

    def _redis_client(self):
        """Return the shared Redis client, or None when unavailable."""
        if not self._redis_init:
            self._redis = _make_redis_client()
            self._redis_init = True
        return self._redis

    def _client_key(self, scope: Scope) -> str:
        user = current_user.get()
        if user and isinstance(user, dict) and user.get("sub"):
            return f"user:{user['sub']}"
        org = current_org_id.get()
        if org:
            return f"org:{org}"
        client = scope.get("client")
        return f"ip:{client[0] if client else 'unknown'}"

    def _redis_key(self, key: str) -> str:
        return f"ratelimit:{self.window_seconds}:{key}"

    # -- checks ------------------------------------------------------------

    def _allow_redis(self, key: str, now: float) -> bool:
        """Fixed-window counter in Redis. Returns None when Redis is down."""
        client = self._redis_client()
        if client is None:
            return None
        rkey = self._redis_key(key)
        try:
            count = client.incr(rkey)
            if count == 1:
                client.expire(rkey, self.window_seconds)
            return count <= self.max_requests
        except Exception:
            # Redis unreachable → fall back to in-process limiter.
            logger.warning("redis rate limiter unavailable; using in-memory fallback")
            return None

    def _allow_memory(self, key: str, now: float) -> bool:
        with self._lock:
            window = self._hits[key]
            cutoff = now - self.window_seconds
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self.max_requests:
                return False
            window.append(now)
            return True

    def _allow(self, key: str, now: float) -> bool:
        allowed = self._allow_redis(key, now)
        if allowed is None:
            return self._allow_memory(key, now)
        return allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        key = self._client_key(scope)
        if not self._allow(key, time.time()):
            logger.warning(_REDIS_NOTE, key)
            body = b'{"detail": "Rate limit exceeded. Try again later."}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)

"""Lightweight per-IP fixed-window rate limiter.

No extra dependency (reuses cachetools). Generous enough for real household
use, tight enough to blunt scripted abuse of the endpoints that fan out to
external APIs and the Groq LLM. Behind the Coolify/Traefik proxy the real
client IP arrives in X-Forwarded-For, so we read that first.
"""
import time

from cachetools import TTLCache
from fastapi import Request
from fastapi.responses import JSONResponse

_WINDOW_S = 60
_MAX_PER_WINDOW = 60          # requests per IP per minute across /api/*
# Key = "<ip>:<minute-bucket>"; entries self-expire after two windows.
_buckets: TTLCache = TTLCache(maxsize=50_000, ttl=_WINDOW_S * 2)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    # Only meter the API; never the health probe (Coolify/Docker hit it often).
    if path.startswith("/api/") and path != "/api/health":
        bucket = int(time.time() // _WINDOW_S)
        key = f"{_client_ip(request)}:{bucket}"
        count = _buckets.get(key, 0) + 1
        _buckets[key] = count
        if count > _MAX_PER_WINDOW:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests — please slow down and try again shortly."},
                headers={"Retry-After": str(_WINDOW_S)},
            )
    return await call_next(request)

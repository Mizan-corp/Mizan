"""Rate limiter for brute-force protection.

Uses Redis when REDIS_URL is set (multi-worker safe), falls back to in-memory
for single-worker / development deployments."""
import logging
import os
import time
import uuid

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_redis = None


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(url, decode_responses=True)
        logger.info("Redis rate limiter connected")
        return _redis
    except Exception as e:
        logger.warning(f"Redis connection failed, falling back to in-memory: {e}")
        return None


class RateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}

    def _get_client_key(self, request: Request) -> str:
        """Extract client identifier - handles proxies via X-Forwarded-For."""
        # Behind Cloudflare (the self-hosted server, reachable only through its tunnel) the
        # client's address is CF-Connecting-IP; X-Forwarded-For's first entry can be forged there.
        cf = request.headers.get("CF-Connecting-IP") if os.environ.get("MIZAN_BEHIND_CLOUDFLARE") else None
        if cf:
            return f"rl:{cf.strip()}"
        # Check X-Forwarded-For first (set by nginx/load balancer)
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            # Take the first IP in the chain (original client)
            client_ip = xff.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        return f"rl:{client_ip}"

    async def __call__(self, request: Request):
        key = self._get_client_key(request)
        r = _get_redis()

        if r:
            await self._check_redis(r, key)
        else:
            await self._check_memory(key)

    async def hit(self, key: str) -> None:
        """Count one attempt under `key` (a user, a workspace, a workspace and an account…) rather
        than the client's address, and refuse (429) once over the limit in the window."""
        key = f"rl:{key}"
        r = _get_redis()
        if r:
            await self._check_redis(r, key)
        else:
            await self._check_memory(key)

    async def count(self, key: str) -> int:
        """The attempts counted under `key` in the current window (without adding one)."""
        key, now = f"rl:{key}", time.time()
        r = _get_redis()
        if r:
            await r.zremrangebyscore(key, 0, now - self.window_seconds)
            return int(await r.zcard(key))
        return len([t for t in self._attempts.get(key, []) if t > now - self.window_seconds])

    async def add(self, key: str) -> None:
        """Count one attempt under `key` without refusing (e.g. one failure)."""
        key, now = f"rl:{key}", time.time()
        r = _get_redis()
        if r:
            pipe = r.pipeline()
            pipe.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
            pipe.expire(key, self.window_seconds)
            await pipe.execute()
        else:
            self._attempts.setdefault(key, []).append(now)

    async def reset(self, key: str) -> None:
        key = f"rl:{key}"
        r = _get_redis()
        if r:
            await r.delete(key)
        else:
            self._attempts.pop(key, None)

    async def _check_redis(self, r, key: str):
        now = time.time()
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window_seconds)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window_seconds)
        results = await pipe.execute()
        count = results[2]
        if count > self.max_requests:
            retry_after = self.window_seconds
            raise HTTPException(
                status_code=429,
                detail=f"محاولات كثيرة جداً. حاول بعد {retry_after} ثانية",
                headers={"Retry-After": str(retry_after)},
            )

    async def _check_memory(self, key: str):
        now = time.time()
        window_start = now - self.window_seconds
        attempts = self._attempts.get(key, [])
        attempts = [t for t in attempts if t > window_start]
        self._attempts[key] = attempts
        if len(attempts) >= self.max_requests:
            retry_after = int(attempts[0] + self.window_seconds - now)
            raise HTTPException(
                status_code=429,
                detail=f"محاولات كثيرة جداً. حاول بعد {retry_after} ثانية",
                headers={"Retry-After": str(retry_after)},
            )
        attempts.append(now)

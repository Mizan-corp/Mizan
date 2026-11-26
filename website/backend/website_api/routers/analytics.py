"""The website's cookieless measurement (ADR-016): one beacon per page view or event.

The browser sends `{"kind", "name", "path", "lang", "ref"?}` as text/plain (a simple request: no
CORS preflight; sendBeacon doesn't read the answer). Only a daily counter goes up: nothing about
the visitor is stored. The address is used in memory to rate-limit, the user agent to skip
crawlers; neither is kept.
"""
import json
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.db.base import get_db
from app.platform.site_analytics import service

router = APIRouter(prefix="/analytics", tags=["analytics"])

beacon_limiter = RateLimiter(max_requests=120, window_seconds=60)


class Beacon(BaseModel):
    kind: Literal["pageview", "event"]
    name: str = Field(max_length=32)
    path: str = Field(max_length=512)
    lang: Literal["ar", "en"]
    ref: str | None = Field(default=None, max_length=253)


@router.post("/event", status_code=204)
async def record_event(request: Request, db: AsyncSession = Depends(get_db), _=Depends(beacon_limiter)):
    # 204 whatever happens: a beacon has no one to read an error, and probing learns nothing.
    done = Response(status_code=204)
    raw = await request.body()
    if len(raw) > 2048 or service.is_bot(request.headers.get("user-agent")):
        return done
    try:
        beacon = Beacon.model_validate(json.loads(raw))
    except (ValueError, ValidationError):
        return done
    path = service.clean_path(beacon.path)
    if path is None:
        return done
    if beacon.kind == "pageview":
        if beacon.name != "page_view":
            return done
        ref = service.clean_host(beacon.ref)
    else:
        if beacon.name not in service.EVENTS:
            return done
        ref = ""
    await service.record(db, kind=beacon.kind, name=beacon.name, path=path, lang=beacon.lang, ref_host=ref)
    return done

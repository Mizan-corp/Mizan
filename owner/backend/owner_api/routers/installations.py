"""Check-ins from single-device and LAN installs (ADR-005).

An install that can reach the internet calls this now and then. The licence key
it holds is its credential: it must be genuine and match a licence here. The
answer carries a fresh key (with the current end date, e.g. after the owner paid)
and whether the licence was revoked.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.licensing.keys import LicenceError, verify
from app.core.ratelimit import RateLimiter
from app.db.base import get_db
from app.platform.licensing.models import Installation, Licence
from app.platform.tenancy.models import Tenant
from app.platform.licensing.services.licences import issue_key, status
from app.platform.auth.services.owners import bypass_rls

router = APIRouter(prefix="/installations", tags=["installations"])

check_in_limiter = RateLimiter(max_requests=30, window_seconds=60)


class CheckIn(BaseModel):
    licence_key: str = Field(min_length=10, max_length=8000)
    installation_id: uuid.UUID
    hostname: str | None = Field(default=None, max_length=128)
    os: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, max_length=32)
    last_backup_at: datetime | None = None


@router.post("/check-in")
async def check_in(data: CheckIn, request: Request, db: AsyncSession = Depends(get_db), _=Depends(check_in_limiter)):
    try:
        claims = verify(data.licence_key)
        licence_id = uuid.UUID(str(claims.get("lid")))
    except (LicenceError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid licence key") from None

    await bypass_rls(db)
    lic = await db.get(Licence, licence_id)
    tenant = await db.get(Tenant, lic.tenant_id) if lic else None
    if lic is None or tenant is None:
        # The workspace was deleted in the cloud.
        return {"status": "revoked", "licence_key": None}

    now = datetime.now(UTC)
    inst = await db.get(Installation, data.installation_id)
    if inst is not None and inst.tenant_id != tenant.id:
        raise HTTPException(status_code=409, detail="Installation id belongs to another workspace")
    if inst is None:
        inst = Installation(id=data.installation_id, tenant_id=tenant.id, licence_id=lic.id, mode=lic.mode, first_seen_at=now)
        db.add(inst)
    inst.hostname, inst.os, inst.app_version = data.hostname, data.os, data.app_version
    inst.last_ip = request.client.host if request.client else None
    inst.last_seen_at = now
    if data.last_backup_at:
        inst.last_backup_at = data.last_backup_at

    state = status(lic, now)
    key = None
    if state != "revoked":
        key, _ = await issue_key(db, tenant)
    await db.commit()
    return {"status": state, "valid_until": lic.valid_until.isoformat(), "licence_key": key}

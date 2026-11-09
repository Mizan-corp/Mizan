"""Helpers shared by the admin routers."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import PlatformAuditLog, Tenant
from app.models.user import User


async def bypass_rls(db: AsyncSession) -> None:
    """Admin reads span every workspace. The setting is transaction-local, so
    call it again after any commit before reading tenant-scoped tables."""
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return tenant


async def record(
    db: AsyncSession,
    actor: User,
    action: str,
    *,
    tenant_id: uuid.UUID | None = None,
    request: Request | None = None,
    **details: Any,
) -> None:
    """Append to the platform audit log and commit.

    The workspace name is stored with the entry so the log stays readable
    after a workspace is renamed or deleted."""
    if tenant_id and "workspace_name" not in details:
        details["workspace_name"] = await db.scalar(select(Tenant.name).where(Tenant.id == tenant_id))
    db.add(PlatformAuditLog(
        id=uuid.uuid4(),
        platform_user_id=actor.id,
        tenant_id=tenant_id,
        action=action,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        details={k: v for k, v in details.items() if v is not None},
    ))
    await db.commit()


async def tenant_names(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(select(Tenant.id, Tenant.name).where(Tenant.id.in_(ids)))).all()
    return dict(rows)


async def user_names(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all()
    return dict(rows)


def iso(value) -> str | None:
    return value.isoformat() if value else None


def days_until(moment) -> int:
    """Whole days until a moment: rounded up while ahead (1.2 days → 2), and
    counted in completed days once past (−1.2 days → −1)."""
    from datetime import UTC, datetime

    seconds = (moment - datetime.now(UTC)).total_seconds()
    return int(-(-seconds // 86400)) if seconds >= 0 else -int(-seconds // 86400)

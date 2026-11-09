"""Platform activity: everything the Mizan team did, newest first."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import iso, tenant_names, user_names
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.models.tenant import PlatformAuditLog
from app.models.user import User

router = APIRouter(prefix="/admoon/activity", tags=["admin: activity"])


async def serialize_logs(db: AsyncSession, rows: list[PlatformAuditLog]) -> list[dict]:
    tenants = await tenant_names(db, {r.tenant_id for r in rows})
    actors = await user_names(db, {r.platform_user_id for r in rows})
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "at": iso(r.created_at),
            "actor": actors.get(r.platform_user_id),
            "tenant_id": str(r.tenant_id) if r.tenant_id else None,
            # Deleted workspaces keep their name in the log details.
            "tenant_name": tenants.get(r.tenant_id) or (r.details or {}).get("workspace_name") or (r.details or {}).get("name"),
            "details": r.details or {},
            "ip": r.ip_address,
        }
        for r in rows
    ]


async def recent_activity(db: AsyncSession, *, limit: int, tenant_id: uuid.UUID | None = None,
                          action: str | None = None, before: str | None = None) -> list[dict]:
    stmt = select(PlatformAuditLog).order_by(PlatformAuditLog.created_at.desc()).limit(limit)
    if tenant_id:
        stmt = stmt.where(PlatformAuditLog.tenant_id == tenant_id)
    if action:
        stmt = stmt.where(PlatformAuditLog.action == action)
    if before:
        stmt = stmt.where(PlatformAuditLog.created_at < before)
    return await serialize_logs(db, list((await db.execute(stmt)).scalars().all()))


@router.get("")
async def list_activity(
    limit: int = Query(50, ge=1, le=200),
    action: str | None = None,
    tenant_id: uuid.UUID | None = None,
    before: str | None = Query(None, description="ISO timestamp; page backwards"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    items = await recent_activity(db, limit=limit, tenant_id=tenant_id, action=action, before=before)
    return {"items": items, "next_before": items[-1]["at"] if len(items) == limit else None}

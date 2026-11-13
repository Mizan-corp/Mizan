"""Activity changes (#107): owners ask in the owner panel; the Mizan team approves (applied at
once) or rejects here. Logic in app.platform.tenancy.activity_change."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import bypass_rls, get_tenant, record
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.platform.auth.models.user import User
from app.platform.tenancy import activity_change as changes
from app.platform.tenancy.context import bind_tenant, unbind_tenant
from app.platform.tenancy.models import Tenant

router = APIRouter(prefix="/admoon/activity-changes", tags=["admin: activity changes"])


@router.get("")
async def list_changes(status: str | None = "requested", db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    stmt = (select(changes.ActivityChange, Tenant.name).join(Tenant, Tenant.id == changes.ActivityChange.tenant_id)
            .order_by(changes.ActivityChange.created_at.desc()).limit(200))
    if status:
        stmt = stmt.where(changes.ActivityChange.status == status)
    return {"items": [changes.out(c, name) for c, name in (await db.execute(stmt)).all()]}


async def _get(db: AsyncSession, change_id: uuid.UUID) -> changes.ActivityChange:
    change = await db.get(changes.ActivityChange, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Request not found")
    return change


@router.get("/{change_id}")
async def get_change(change_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    """The request, with what it does today (an open one)."""
    change = await _get(db, change_id)
    tenant = await get_tenant(db, change.tenant_id)
    out = changes.out(change, tenant.name)
    if change.status == "requested":
        try:
            out["preview"] = await changes.preview(db, tenant, change.to_activity)
        except HTTPException as e:
            out["preview_error"] = e.detail
        finally:
            await db.rollback()
            await unbind_tenant(db)
    return out


class Decision(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@router.post("/{change_id}/approve")
async def approve(change_id: uuid.UUID, body: Decision, request: Request, db: AsyncSession = Depends(get_db),
                  admin: User = Depends(require_superadmin)):
    """Approve and apply: the activity switches, modules leave and join, as previewed."""
    from app.platform.notifications.models.notification import Notification

    change = await _get(db, change_id)
    tenant = await get_tenant(db, change.tenant_id)
    admin_id, tenant_id, to_name = admin.id, tenant.id, changes._name(change.to_activity)
    result = await changes.apply(db, change, tenant, admin_id)  # commits the workspace's changes

    await bind_tenant(db, tenant_id)
    db.add(Notification(
        tenant_id=tenant_id, title="تغيّر نشاط المنشأة",
        body=f"أصبح نشاط مساحة العمل «{to_name}». القوائم والشاشات تتبع النشاط الجديد.",
        type="system", severity="info",
    ))
    await db.commit()
    await unbind_tenant(db)

    await bypass_rls(db)  # transaction-local: again after the commits above
    change = await _get(db, change_id)
    change.status, change.decided_by, change.decided_at = "applied", admin_id, datetime.now(UTC)
    change.decision_note, change.result = body.note, result
    await db.commit()
    await record(db, admin, "activity_changed", tenant_id=tenant_id, request=request,
                 from_activity=result["from"], to_activity=result["to"], removed=result["removed"], added=result["added"],
                 data_mode=result["data_mode"])
    return changes.out(change)


@router.post("/{change_id}/reject")
async def reject(change_id: uuid.UUID, body: Decision, request: Request, db: AsyncSession = Depends(get_db),
                 admin: User = Depends(require_superadmin)):
    change = await _get(db, change_id)
    if change.status != "requested":
        raise HTTPException(status_code=409, detail="This request was already decided")
    if not (body.note or "").strip():
        raise HTTPException(status_code=422, detail="Say why, for the owner")
    change.status, change.decided_by, change.decided_at, change.decision_note = "rejected", admin.id, datetime.now(UTC), body.note.strip()
    await db.commit()
    await record(db, admin, "activity_change_rejected", tenant_id=change.tenant_id, request=request,
                 to_activity=change.to_activity, note=change.decision_note)
    return changes.out(change)

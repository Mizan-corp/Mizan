"""Changing a workspace's activity, from the owner's side (#107): see what it does, ask, cancel.
The Mizan team approves in the admin panel (app.platform.tenancy.activity_change)."""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.services.owners import bypass_rls, get_current_owner, owned_workspace
from app.platform.tenancy import activity_change as changes
from app.platform.tenancy.context import unbind_tenant

router = APIRouter(prefix="/account/workspaces", tags=["activity change"])
catalogue = APIRouter(prefix="/account/activities", tags=["activity change"])


@catalogue.get("/developers")
async def developer_activities(_: OwnerAccount = Depends(get_current_owner)):
    """Developers' activities a workspace can change to (ADR-012): approved and listed."""
    from app.framework import package_activities

    await package_activities.ensure_fresh()
    return {"items": [
        {"id": d.id, "name": d.manifest.get("name"), "name_en": d.manifest.get("name_en"), "description": d.manifest.get("description"),
         "family": d.manifest.get("family"), "icon": d.manifest.get("icon"), "developer": d.developer, "version": d.version}
        for d in sorted(package_activities.all_defs().values(), key=lambda d: d.manifest.get("name") or d.id)
        if d.listed and not d.revoked]}


@router.get("/{tenant_id}/activity-change/preview")
async def preview(tenant_id: uuid.UUID, to: str, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    """What changing to `to` would do: modules leaving (with their records), joining, working differently."""
    from app.framework import package_activities

    t = await owned_workspace(db, owner, tenant_id)
    await package_activities.ensure_fresh()
    try:
        return await changes.preview(db, t, to)
    finally:
        await db.rollback()
        await unbind_tenant(db)


@router.get("/{tenant_id}/activity-change")
async def latest(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    """The workspace's latest request (open, or the last decision), or null."""
    await owned_workspace(db, owner, tenant_id)
    await bypass_rls(db)  # activity_changes has RLS; reads here are the owner's own workspace
    row = await db.scalar(select(changes.ActivityChange).where(changes.ActivityChange.tenant_id == tenant_id)
                          .order_by(changes.ActivityChange.created_at.desc()).limit(1))
    return {"change": changes.out(row) if row else None}


class ChangeRequest(BaseModel):
    to: str = Field(min_length=2, max_length=80)
    data_mode: Literal["keep", "delete"] = "keep"
    note: str | None = Field(default=None, max_length=1000)


@router.post("/{tenant_id}/activity-change", status_code=201)
async def ask(tenant_id: uuid.UUID, body: ChangeRequest, db: AsyncSession = Depends(get_db),
              owner: OwnerAccount = Depends(get_current_owner)):
    t = await owned_workspace(db, owner, tenant_id)
    await bypass_rls(db)  # activity_changes has RLS; reads here are the owner's own workspace
    if t.status == "suspended":
        raise HTTPException(status_code=403, detail="مساحة العمل هذه موقوفة. تواصل مع الدعم أولًا.")
    change = await changes.request(db, t, owner.id, body.to, body.data_mode, body.note)
    await db.commit()
    return {"change": changes.out(change)}


@router.delete("/{tenant_id}/activity-change", status_code=204)
async def cancel(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    await owned_workspace(db, owner, tenant_id)
    await bypass_rls(db)  # activity_changes has RLS; reads here are the owner's own workspace
    open_ = await changes.open_request(db, tenant_id)
    if not open_:
        raise HTTPException(status_code=404, detail="لا يوجد طلب قيد المراجعة")
    open_.status = "cancelled"
    await db.commit()

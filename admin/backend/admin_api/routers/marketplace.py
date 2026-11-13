"""Marketplace review (ADR-007 milestone 2, #105): the Mizan team approves (countersigns and lists)
or rejects developers' submissions, and can delist a listing. Logic in app.platform.marketplace.listings."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import record
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.platform.auth.models.user import User
from app.platform.developers.models import DeveloperTeam
from app.platform.marketplace import listings
from app.platform.marketplace.listings import MarketplaceItem, MarketplaceVersion
from app.platform.tenancy.models import Tenant

router = APIRouter(prefix="/admoon/marketplace", tags=["admin: marketplace"])


@router.get("/submissions")
async def submissions(status: str | None = "in_review", db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    stmt = (select(MarketplaceVersion, DeveloperTeam.handle).join(DeveloperTeam, DeveloperTeam.id == MarketplaceVersion.team_id)
            .order_by(MarketplaceVersion.submitted_at.desc()).limit(200))
    if status:
        stmt = stmt.where(MarketplaceVersion.status == status)
    return {"items": [{**listings.version_out(v), "developer": h} for v, h in (await db.execute(stmt)).all()]}


async def _version(db: AsyncSession, version_id: uuid.UUID) -> MarketplaceVersion:
    v = await db.get(MarketplaceVersion, version_id)
    if not v:
        raise HTTPException(404, "Submission not found")
    return v


@router.get("/submissions/{version_id}")
async def submission(version_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    """What the reviewer needs: the manifest, what it adds and may access, its files, earlier versions."""
    from app.framework import package as mzm
    from app.platform.community import service as community

    v = await _version(db, version_id)
    handle = await db.scalar(select(DeveloperTeam.handle).where(DeveloperTeam.id == v.team_id))
    files, _sig = mzm.read_unverified(v.package)
    out = {**listings.version_out(v), "developer": handle, "manifest": v.manifest,
           "files": sorted(({"name": n, "size": len(b)} for n, b in files.items()), key=lambda f: f["name"])}
    try:
        pkg = mzm.verify(v.package)
        if v.kind == "community":
            out["summary"] = community.summary(pkg, None)
        elif v.kind == "activity":
            out["activity"] = activity_summary(pkg)
            out["workspaces"] = await db.scalar(select(func.count()).select_from(Tenant).where(Tenant.sector == v.item_id))
        else:
            from app.platform.themes import service as themes

            out["theme"] = themes.package_summary(pkg, None)
    except mzm.PackageError as e:
        out["verify_error"] = str(e)
    previous = await db.scalar(select(MarketplaceItem.current_version).where(MarketplaceItem.id == v.item_id))
    out["listed_version"] = previous
    if previous and "summary" in out:
        before = await db.scalar(select(MarketplaceVersion.manifest).where(MarketplaceVersion.item_id == v.item_id,
                                                                           MarketplaceVersion.version == previous))
        had = set((before or {}).get("scopes") or [])
        for s in out["summary"]["scopes"]:
            s["new"] = s["id"] not in had
    return out


def activity_summary(pkg) -> dict:
    """What a developer's activity brings (ADR-012), for the reviewer."""
    from app.framework import package_activities
    from app.framework.loader import manifest_index

    d = package_activities.from_package(pkg)
    names = manifest_index()
    m = d.manifest
    return {
        "family": m.get("family"), "home": m.get("home"), "theme": m.get("theme"),
        "modules": [{"id": x, "name": names.get(x, {}).get("name_en") or x} for x in d.activity["modules"]],
        "optional": [{"id": x, "name": names.get(x, {}).get("name_en") or x} for x in d.activity["optional"]],
        "own_modules": [{"id": mid, "name": p.manifest.get("name_en") or p.manifest.get("name"), "entities": len(p.entities),
                         "scopes": list(p.manifest.get("scopes") or []), "sends_to": ((p.manifest.get("webhooks") or {}).get("url") or "").split("/")[2]
                         if (p.manifest.get("webhooks") or {}).get("url") else None} for mid, p in d.modules.items()],
        "variants": [{"module": mod, "fields": sum(len(f) for f in (v.get("fields") or {}).values()),
                      "terms": len(v.get("terms") or {}), "settings": len(v.get("settings") or {})} for mod, v in d.variants.items()],
        "themes": [{"id": t.manifest["id"], "name": t.manifest.get("name_en") or t.manifest.get("name")} for t in d.themes.values()],
        "positions": [p.get("name_en") for p in m.get("positions") or []],
        "menu_groups": len(m.get("menu") or []),
        "seed_records": sum(len(x.get("records") or []) for x in d.seed),
    }


class Decision(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@router.post("/submissions/{version_id}/approve")
async def approve(version_id: uuid.UUID, body: Decision, request: Request, db: AsyncSession = Depends(get_db),
                  admin: User = Depends(require_superadmin)):
    v = await _version(db, version_id)
    item = await listings.approve(db, v, admin.id, body.note)
    await db.commit()
    updated: list[str] = []
    if v.kind == "activity":  # ADR-012: reload it here at once; workspaces running it follow
        from app.framework import package_activities
        from app.platform.tenancy.activity_change import follow_update

        await package_activities.refresh(force=True)
        updated = await follow_update(db, v.item_id)
    await record(db, admin, "marketplace_approved", request=request, item=v.item_id, version=v.version, kind=v.kind,
                 workspaces_updated=len(updated))
    return {**listings.version_out(v), "listing": listings.item_out(item), "workspaces_updated": len(updated)}


@router.post("/submissions/{version_id}/reject")
async def reject(version_id: uuid.UUID, body: Decision, request: Request, db: AsyncSession = Depends(get_db),
                 admin: User = Depends(require_superadmin)):
    v = await _version(db, version_id)
    await listings.reject(db, v, admin.id, body.note or "")
    await db.commit()
    await record(db, admin, "marketplace_rejected", request=request, item=v.item_id, version=v.version, note=v.review_note)
    return listings.version_out(v)


@router.get("/items")
async def items(db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    rows = (await db.execute(select(MarketplaceItem, DeveloperTeam.handle).join(DeveloperTeam, DeveloperTeam.id == MarketplaceItem.team_id)
                             .order_by(MarketplaceItem.updated_at.desc()))).all()
    return {"items": [listings.item_out(i, h) for i, h in rows]}


@router.post("/items/{item_id}/{action}")
async def set_listed(item_id: str, action: str, body: Decision, request: Request, db: AsyncSession = Depends(get_db),
                     admin: User = Depends(require_superadmin)):
    """delist (hide from the store; installs stay) or relist."""
    if action not in ("delist", "relist"):
        raise HTTPException(404, "Unknown action")
    if action == "delist" and not (body.note or "").strip():
        raise HTTPException(422, "Say why")
    item = await listings.set_listed(db, item_id, action == "relist", body.note)
    await db.commit()
    if item.kind == "activity":  # a delisted activity can't be switched to; workspaces on it keep it
        from app.framework import package_activities

        await package_activities.refresh(force=True)
    await record(db, admin, f"marketplace_{action}ed", request=request, item=item_id, note=body.note)
    return listings.item_out(item)

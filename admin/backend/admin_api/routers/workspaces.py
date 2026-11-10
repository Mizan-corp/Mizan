"""Workspaces (tenants): find, inspect and manage every company on Mizan."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import days_until, get_tenant, iso, record
from admin_api.routers.activity import recent_activity
from app.core.modules import set_active_modules
from app.catalog import canonical_activity, canonical_modules, family_of
from app.framework.loader import manifest_index
from app.core.plans import PLANS_CONFIG, get_plan_limits
from app.core.sectors import SECTORS
from app.core.security import hash_password
from app.core.tenancy import bind_tenant
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.models.billing import BillingInvoice
from app.models.product import Product
from app.models.sale import Sale
from app.models.tenant import Subscription, Tenant
from app.models.user import User
from app.models.warehouse import Warehouse
from app.platform.auth.services import auth as auth_service
from app.models.owner import OwnerAccount
from app.platform.auth.services.owners import normalize_login
from app.platform.tenancy.service import create_workspace as new_workspace
from app.platform.billing.services.subscriptions import monthly_price
from app.core.licensing import LicenceError
from app.models.licence import Installation
from app.platform.licensing.services.licences import ensure_licence, get_licence, is_on_premise, issue_key
from app.platform.licensing.services.licences import status as licence_status

router = APIRouter(prefix="/admoon", tags=["admin: workspaces"])

TRIAL_DAYS = 14


# ─── Serialization ─────────────────────────────────────────────────────────


def _trial_days_left(t: Tenant) -> int | None:
    if t.plan != "trial" or not t.trial_ends_at:
        return None
    return days_until(t.trial_ends_at)


def _summary(t: Tenant) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "sector": t.sector,
        "status": t.status,
        "plan": t.plan,
        "monthly_price_egp": monthly_price(t.plan),
        "trial_ends_at": iso(t.trial_ends_at),
        "trial_days_left": _trial_days_left(t),
        "created_at": iso(t.created_at),
        "deployment_mode": t.deployment_mode,
    }


# ─── List ──────────────────────────────────────────────────────────────────


@router.get("/tenants")
async def list_workspaces(
    q: str | None = None,
    status: Literal["active", "suspended", "trial", "paying"] | None = None,
    sector: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    stmt = select(Tenant).order_by(Tenant.created_at.desc())
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(Tenant.name).like(like) | func.lower(func.coalesce(Tenant.slug, "")).like(like))
    if status == "trial":
        stmt = stmt.where(Tenant.plan == "trial", Tenant.status != "suspended")
    elif status == "paying":
        stmt = stmt.where(Tenant.plan != "trial", Tenant.status == "active")
    elif status:
        stmt = stmt.where(Tenant.status == status)
    if sector:
        stmt = stmt.where(Tenant.sector == sector)
    tenants = (await db.execute(stmt)).scalars().all()

    users = dict((await db.execute(select(User.tenant_id, func.count(User.id)).group_by(User.tenant_id))).all())
    sales = {
        tid: (count, float(volume or 0), last)
        for tid, count, volume, last in (await db.execute(
            select(Sale.tenant_id, func.count(Sale.id), func.sum(Sale.net_total), func.max(Sale.created_at))
            .group_by(Sale.tenant_id)
        )).all()
    }
    items = []
    for t in tenants:
        count, volume, last = sales.get(t.id, (0, 0.0, None))
        items.append({
            **_summary(t),
            "users_count": users.get(t.id, 0),
            "sales_count": count,
            "sales_volume_egp": volume,
            "last_sale_at": iso(last),
        })
    return {"items": items, "sectors": sorted({t.sector for t in tenants} | set(SECTORS[:30]))}


# ─── Detail ────────────────────────────────────────────────────────────────


@router.get("/tenants/{tenant_id}")
async def get_workspace(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    t = await get_tenant(db, tenant_id)
    users = (await db.execute(select(User).where(User.tenant_id == t.id).order_by(User.created_at))).scalars().all()
    branches = (await db.execute(select(Warehouse).where(Warehouse.tenant_id == t.id).order_by(Warehouse.created_at))).scalars().all()
    products = await db.scalar(select(func.count(Product.id)).where(Product.tenant_id == t.id)) or 0
    sales_count, sales_volume, last_sale = (await db.execute(
        select(func.count(Sale.id), func.coalesce(func.sum(Sale.net_total), 0), func.max(Sale.created_at)).where(Sale.tenant_id == t.id)
    )).one()
    invoices = (await db.execute(
        select(BillingInvoice).where(BillingInvoice.tenant_id == t.id).order_by(BillingInvoice.created_at.desc()).limit(20)
    )).scalars().all()
    requests = (await db.execute(
        select(Subscription).where(Subscription.tenant_id == t.id).order_by(Subscription.created_at.desc()).limit(20)
    )).scalars().all()
    owner = next((u for u in users if u.role == "admin"), users[0] if users else None)

    return {
        "workspace": {
            **_summary(t),
            "scale": t.scale,
            "active_modules": t.active_modules or [],
            "limits": t.limits or {},
            "system_path": f"/c/{t.slug}" if t.slug else None,
        },
        "owner": {"id": str(owner.id), "username": owner.username, "full_name": owner.full_name} if owner else None,
        "stats": {
            "users": len(users),
            "branches": len(branches),
            "products": products,
            "sales": sales_count,
            "sales_volume_egp": float(sales_volume),
            "last_sale_at": iso(last_sale),
        },
        "users": [
            {"id": str(u.id), "username": u.username, "full_name": u.full_name, "role": u.role,
             "is_active": u.is_active, "created_at": iso(u.created_at)}
            for u in users
        ],
        "branches": [{"id": str(w.id), "name": w.name, "is_active": w.is_active} for w in branches],
        "invoices": [
            {"ref": i.invoice_ref, "plan": i.plan, "cycle": i.billing_cycle, "amount_egp": i.amount_egp,
             "status": i.status, "method": i.payment_method, "created_at": iso(i.created_at), "paid_at": iso(i.paid_at)}
            for i in invoices
        ],
        "requests": [
            {"id": str(r.id), "plan": r.plan, "status": r.status, "phone": r.contact_phone, "created_at": iso(r.created_at)}
            for r in requests
        ],
        "activity": await recent_activity(db, limit=20, tenant_id=t.id),
        **await _licence_block(db, t),
    }


# ─── Licence & installations (single-device and LAN workspaces) ────────────


async def _licence_block(db: AsyncSession, t: Tenant) -> dict:
    lic = await get_licence(db, t.id)
    installs = (await db.execute(
        select(Installation).where(Installation.tenant_id == t.id).order_by(Installation.last_seen_at.desc())
    )).scalars().all()
    return {
        "licence": None if lic is None else {
            "id": str(lic.id), "mode": lic.mode, "status": licence_status(lic),
            "valid_until": iso(lic.valid_until), "revoked_at": iso(lic.revoked_at),
        },
        "installations": [
            {"id": str(i.id), "hostname": i.hostname, "os": i.os, "app_version": i.app_version, "last_ip": i.last_ip,
             "first_seen_at": iso(i.first_seen_at), "last_seen_at": iso(i.last_seen_at), "last_backup_at": iso(i.last_backup_at)}
            for i in installs
        ],
    }


async def _on_premise(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    t = await get_tenant(db, tenant_id)
    if not is_on_premise(t):
        raise HTTPException(status_code=409, detail="This workspace runs in the cloud and has no licence")
    return t


class ExtendLicence(BaseModel):
    days: int = Field(ge=1, le=3660)
    reason: str | None = Field(default=None, max_length=500)


@router.post("/tenants/{tenant_id}/licence/extend")
async def extend_licence(
    tenant_id: uuid.UUID, body: ExtendLicence, request: Request,
    db: AsyncSession = Depends(get_db), admin: User = Depends(require_superadmin),
):
    t = await _on_premise(db, tenant_id)
    lic = await ensure_licence(db, t)
    before = lic.valid_until
    lic.valid_until = max(lic.valid_until, datetime.now(UTC)) + timedelta(days=body.days)
    await db.commit()
    await record(db, admin, "licence_extended", tenant_id=t.id, request=request, days=body.days,
                 old_until=iso(before), new_until=iso(lic.valid_until), reason=body.reason)
    return {"ok": True, "valid_until": iso(lic.valid_until)}


class RevokeLicence(BaseModel):
    revoked: bool
    reason: str | None = Field(default=None, max_length=500)


@router.post("/tenants/{tenant_id}/licence/revoke")
async def revoke_licence(
    tenant_id: uuid.UUID, body: RevokeLicence, request: Request,
    db: AsyncSession = Depends(get_db), admin: User = Depends(require_superadmin),
):
    t = await _on_premise(db, tenant_id)
    lic = await ensure_licence(db, t)
    lic.revoked_at = datetime.now(UTC) if body.revoked else None
    await db.commit()
    await record(db, admin, "licence_revoked" if body.revoked else "licence_restored", tenant_id=t.id,
                 request=request, reason=body.reason)
    return {"ok": True, "status": licence_status(lic)}


@router.post("/tenants/{tenant_id}/licence/key")
async def licence_key(
    tenant_id: uuid.UUID, request: Request,
    db: AsyncSession = Depends(get_db), admin: User = Depends(require_superadmin),
):
    """A key to type into an install that's never online."""
    t = await _on_premise(db, tenant_id)
    try:
        key, lic = await issue_key(db, t)
    except LicenceError as e:
        raise HTTPException(status_code=503, detail=f"Can't sign licences here: {e}") from None
    await db.commit()
    await record(db, admin, "licence_key_issued", tenant_id=t.id, request=request, valid_until=iso(lic.valid_until))
    return {"licence_key": key, "valid_until": iso(lic.valid_until)}


# ─── Create ────────────────────────────────────────────────────────────────


class CreateWorkspace(BaseModel):
    company_name: str = Field(min_length=2, max_length=128)
    sector: str = "retail"
    scale: Literal["small", "medium", "large"] = "small"
    slug: str | None = Field(default=None, max_length=48, pattern=r"^[a-z0-9-]*$")
    plan: str = "trial"
    trial_days: int = Field(default=TRIAL_DAYS, ge=1, le=365)
    owner_full_name: str = Field(min_length=2, max_length=128)
    owner_username: str = Field(min_length=3, max_length=64, pattern=r"^[\w.\-]+$")
    owner_password: str = Field(min_length=8, max_length=128)
    demo_data: bool = False
    deployment_mode: Literal["cloud_saas", "desktop", "lan"] = "cloud_saas"


@router.post("/tenants", status_code=201)
async def create_workspace(
    data: CreateWorkspace,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    data.sector = canonical_activity(data.sector)
    if data.sector not in SECTORS:
        raise HTTPException(status_code=422, detail="Unknown business type")
    if data.plan not in PLANS_CONFIG:
        raise HTTPException(status_code=422, detail="Unknown plan")
    if await db.scalar(select(OwnerAccount.id).where(OwnerAccount.login == normalize_login(data.owner_username))):
        raise HTTPException(status_code=409, detail="An owner account already uses this username")
    password_hash = hash_password(data.owner_password)
    account = OwnerAccount(
        id=uuid.uuid4(), login=normalize_login(data.owner_username),
        full_name=data.owner_full_name.strip(), password_hash=password_hash,
    )
    db.add(account)
    await db.flush()
    tenant, _ = await new_workspace(
        db, name=data.company_name, sector=data.sector, scale=data.scale, slug=data.slug or None,
        plan=data.plan, trial_days=data.trial_days, demo_data=data.demo_data, owner=account,
        deployment_mode=data.deployment_mode,
        admin_username=data.owner_username, admin_full_name=data.owner_full_name, admin_password_hash=password_hash,
    )
    await db.commit()

    await record(db, admin, "tenant_created", tenant_id=tenant.id, request=request,
                 name=tenant.name, slug=tenant.slug, plan=data.plan, sector=data.sector, mode=data.deployment_mode)
    return {"id": str(tenant.id), "slug": tenant.slug}


# ─── Edit ──────────────────────────────────────────────────────────────────


class UpdateWorkspace(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=128)
    slug: str | None = Field(default=None, min_length=3, max_length=48, pattern=r"^[a-z0-9-]+$")


@router.patch("/tenants/{tenant_id}")
async def update_workspace(
    tenant_id: uuid.UUID,
    data: UpdateWorkspace,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    t = await get_tenant(db, tenant_id)
    changes = {}
    if data.name and data.name.strip() != t.name:
        changes["name"] = [t.name, data.name.strip()]
        t.name = data.name.strip()
    if data.slug and data.slug != t.slug:
        if await db.scalar(select(Tenant.id).where(Tenant.slug == data.slug, Tenant.id != t.id)):
            raise HTTPException(status_code=409, detail="Another workspace already uses this URL name")
        changes["slug"] = [t.slug, data.slug]
        t.slug = data.slug
    await db.commit()
    if changes:
        await record(db, admin, "tenant_updated", tenant_id=t.id, request=request, changes=changes)
    return {"ok": True}


class SetStatus(BaseModel):
    status: Literal["active", "suspended"]
    reason: str | None = Field(default=None, max_length=500)


@router.post("/tenants/{tenant_id}/status")
async def set_status(
    tenant_id: uuid.UUID,
    body: SetStatus,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    t = await get_tenant(db, tenant_id)
    old, t.status = t.status, body.status
    await db.commit()
    await record(db, admin, "tenant_status_change", tenant_id=t.id, request=request,
                 old_status=old, new_status=body.status, reason=body.reason)
    return {"ok": True, "status": body.status}


class SetPlan(BaseModel):
    plan: str
    trial_days: int | None = Field(default=None, ge=1, le=365)
    reason: str | None = Field(default=None, max_length=500)


@router.post("/tenants/{tenant_id}/plan")
async def set_plan(
    tenant_id: uuid.UUID,
    body: SetPlan,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    if body.plan not in PLANS_CONFIG:
        raise HTTPException(status_code=422, detail="Unknown plan")
    t = await get_tenant(db, tenant_id)
    old = t.plan
    t.plan, t.limits = body.plan, get_plan_limits(body.plan)
    t.trial_ends_at = (datetime.now(UTC) + timedelta(days=body.trial_days or TRIAL_DAYS)) if body.plan == "trial" else None
    await db.commit()
    await record(db, admin, "tenant_plan_updated", tenant_id=t.id, request=request,
                 old_plan=old, new_plan=body.plan, reason=body.reason)
    return {"ok": True}


class ExtendTrial(BaseModel):
    days: int = Field(ge=1, le=90)


@router.post("/tenants/{tenant_id}/extend-trial")
async def extend_trial(
    tenant_id: uuid.UUID,
    body: ExtendTrial,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    t = await get_tenant(db, tenant_id)
    if t.plan != "trial":
        raise HTTPException(status_code=409, detail="This workspace isn't on a trial")
    start = max(t.trial_ends_at or datetime.now(UTC), datetime.now(UTC))
    t.trial_ends_at = start + timedelta(days=body.days)
    await db.commit()
    await record(db, admin, "trial_extended", tenant_id=t.id, request=request, days=body.days, until=iso(t.trial_ends_at))
    return {"ok": True, "trial_ends_at": iso(t.trial_ends_at)}


# ─── Modules ───────────────────────────────────────────────────────────────


def module_catalog() -> list[dict]:
    """Every module from its manifest.json (no module code is imported)."""
    return [
        {"id": mid, "name": m.get("name", mid), "name_en": m.get("name_en", ""),
         "category": family_of(m.get("activity", "")) or "", "activity": m.get("activity", "")}
        for mid, m in sorted(manifest_index().items())
        if m.get("kind", "business") != "platform"  # always on, never toggled
    ]


@router.get("/modules")
async def list_modules(_: User = Depends(require_superadmin)):
    return {"items": module_catalog()}


class SetModules(BaseModel):
    active_modules: list[str]


@router.put("/tenants/{tenant_id}/modules")
async def set_modules(
    tenant_id: uuid.UUID,
    body: SetModules,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    body.active_modules = canonical_modules(body.active_modules)
    known = {m["id"] for m in module_catalog()}
    unknown = set(body.active_modules) - known - {"pos", "inventory", "sales", "finance", "hr", "operations", "purchases", "contacts"}
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown modules: {', '.join(sorted(unknown))}")
    t = await get_tenant(db, tenant_id)
    before = set(t.active_modules or [])
    t.active_modules = list(dict.fromkeys(body.active_modules))
    await bind_tenant(db, t.id)
    await set_active_modules(db, t.active_modules)
    await db.commit()
    after = set(t.active_modules)
    await record(db, admin, "tenant_modules_updated", tenant_id=t.id, request=request,
                 added=sorted(after - before), removed=sorted(before - after))
    return {"ok": True, "active_modules": t.active_modules}


# ─── Open as owner ─────────────────────────────────────────────────────────


@router.post("/tenants/{tenant_id}/impersonate")
async def open_as_owner(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    t = await get_tenant(db, tenant_id)
    owner = (await db.execute(
        select(User).where(User.tenant_id == t.id, User.is_active.is_(True))
        .order_by((User.role == "admin").desc(), User.created_at).limit(1)
    )).scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=404, detail="This workspace has no active user to sign in as")
    token = auth_service.issue_token(owner)["access_token"]
    await record(db, admin, "tenant_impersonated", tenant_id=t.id, request=request, as_user=owner.username)
    # No cookie: the token is handed to the system app explicitly and never
    # replaces the admin's own session in this browser.
    return {"access_token": token, "slug": t.slug, "as_user": owner.username}


# ─── Delete ────────────────────────────────────────────────────────────────


@router.delete("/tenants/{tenant_id}")
async def delete_workspace(
    tenant_id: uuid.UUID,
    request: Request,
    confirm: str = Query(..., description="The workspace's slug, typed to confirm"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    t = await get_tenant(db, tenant_id)
    if confirm != (t.slug or str(t.id)):
        raise HTTPException(status_code=400, detail="Type the workspace's URL name exactly to confirm deletion")
    name, slug = t.name, t.slug
    await db.delete(t)
    await db.commit()
    await record(db, admin, "tenant_deleted", tenant_id=tenant_id, request=request, name=name, slug=slug, workspace_name=name)
    return {"ok": True}


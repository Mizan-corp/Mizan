"""The owner's workspaces: list, create, details and opening one in the app."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.billing.plans import get_plan
from app.catalog import canonical_activity
from app.catalog.sectors import SECTORS
from app.db.base import get_db
from app.platform.billing.models import BillingInvoice
from app.platform.auth.models.owner import OwnerAccount
from app.modules.general.sales.models.sale import Sale
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User
from app.platform.auth.services import auth as auth_service
from app.platform.auth.services.owners import get_current_owner, owned_workspace, workspace_user
from app.platform.billing.services.plan_gating import get_tenant_limits_and_usage
from app.platform.billing.services.subscriptions import paid_until
from app.platform.tenancy.service import create_workspace
from app.platform.licensing.keys import LicenceError
from app.platform.updates.releases import published_installers
from app.platform.licensing.models import Installation, Licence
from app.platform.licensing.services.licences import get_licence, is_on_premise, issue_key
from app.platform.licensing.services.licences import status as licence_status
from owner_api.common import days_until, invoice_out, iso

router = APIRouter(prefix="/account/workspaces", tags=["workspaces"])

MAX_WORKSPACES = 10
MAX_TRIALS = 3


def licence_out(lic: Licence | None, installs: list[Installation] | None = None) -> dict | None:
    if lic is None:
        return None
    installs = installs or []
    return {
        "status": licence_status(lic),
        "valid_until": iso(lic.valid_until),
        "installations": len(installs),
        "last_seen_at": iso(max((i.last_seen_at for i in installs), default=None)),
    }


def summary(
    t: Tenant,
    *,
    users: int = 0,
    last_sale: datetime | None = None,
    until: datetime | None = None,
    lic: Licence | None = None,
    installs: list[Installation] | None = None,
) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "sector": t.sector,
        "status": t.status,
        "plan": t.plan,
        "monthly_price_egp": get_plan(t.plan)["price_monthly_egp"],
        "trial_ends_at": iso(t.trial_ends_at),
        "trial_days_left": days_until(t.trial_ends_at) if t.plan == "trial" and t.trial_ends_at else None,
        "paid_until": iso(t.paid_until or until),  # the column the read-only rule uses (#66)
        "users_count": users,
        "last_sale_at": iso(last_sale),
        "created_at": iso(t.created_at),
        "deployment_mode": t.deployment_mode,
        "licence": licence_out(lic, installs),
    }


@router.get("")
async def list_workspaces(db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    tenants = (await db.execute(
        select(Tenant).where(Tenant.owner_account_id == owner.id).order_by(Tenant.created_at)
    )).scalars().all()
    ids = [t.id for t in tenants]
    if not ids:
        return {"items": []}
    users = dict((await db.execute(
        select(User.tenant_id, func.count(User.id)).where(User.tenant_id.in_(ids), User.is_active.is_(True)).group_by(User.tenant_id)
    )).all())
    last_sale = dict((await db.execute(
        select(Sale.tenant_id, func.max(Sale.created_at)).where(Sale.tenant_id.in_(ids)).group_by(Sale.tenant_id)
    )).all())
    until = dict((await db.execute(
        select(BillingInvoice.tenant_id, func.max(BillingInvoice.period_end))
        .where(BillingInvoice.tenant_id.in_(ids), BillingInvoice.status == "paid").group_by(BillingInvoice.tenant_id)
    )).all())
    lics = {lic.tenant_id: lic for lic in (await db.execute(select(Licence).where(Licence.tenant_id.in_(ids)))).scalars()}
    installs: dict = {}
    for inst in (await db.execute(select(Installation).where(Installation.tenant_id.in_(ids)))).scalars():
        installs.setdefault(inst.tenant_id, []).append(inst)
    return {"items": [
        summary(t, users=users.get(t.id, 0), last_sale=last_sale.get(t.id), until=until.get(t.id),
                lic=lics.get(t.id), installs=installs.get(t.id))
        for t in tenants
    ]}


class NewWorkspace(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    sector: str
    scale: Literal["small", "medium", "large"] = "small"
    demo_data: bool = True
    # cloud_saas: in the browser; desktop: one computer; lan: a server on the local network.
    mode: Literal["cloud_saas", "desktop", "lan"] = "cloud_saas"


@router.post("", status_code=201)
async def new_workspace(data: NewWorkspace, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    data.sector = canonical_activity(data.sector)
    if data.sector not in SECTORS:
        raise HTTPException(status_code=422, detail="نشاط غير معروف")
    owned = (await db.execute(select(Tenant.plan, Tenant.trial_ends_at).where(Tenant.owner_account_id == owner.id))).all()
    if len(owned) >= MAX_WORKSPACES:
        raise HTTPException(status_code=409, detail=f"وصلت للحد الأقصى ({MAX_WORKSPACES} مساحات عمل). تواصل معنا لزيادته.")
    now = datetime.now(UTC)
    if sum(1 for plan, ends in owned if plan == "trial" and ends and ends > now) >= MAX_TRIALS:
        raise HTTPException(
            status_code=409,
            detail=f"لديك {MAX_TRIALS} مساحات عمل في الفترة التجريبية. اشترك في إحداها قبل إنشاء مساحة جديدة.",
        )
    # The owner signs in to the new workspace with the same name and password.
    # Single-device/LAN: only registered here; the installer creates it on site.
    tenant, _ = await create_workspace(
        db, name=data.name, sector=data.sector, scale=data.scale, demo_data=data.demo_data, owner=owner,
        admin_username=owner.login, admin_full_name=owner.full_name, admin_password_hash=owner.password_hash,
        deployment_mode=data.mode,
    )
    lic = await get_licence(db, tenant.id)
    await db.commit()
    return summary(tenant, users=0 if lic else 1, lic=lic)


@router.get("/{tenant_id}")
async def workspace_detail(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    t = await owned_workspace(db, owner, tenant_id)
    usage = await get_tenant_limits_and_usage(db, t.id)
    invoices = (await db.execute(
        select(BillingInvoice).where(BillingInvoice.tenant_id == t.id).order_by(BillingInvoice.created_at.desc()).limit(50)
    )).scalars().all()
    last_sale = await db.scalar(select(func.max(Sale.created_at)).where(Sale.tenant_id == t.id))
    lic = await get_licence(db, t.id)
    installs = (await db.execute(
        select(Installation).where(Installation.tenant_id == t.id).order_by(Installation.last_seen_at.desc())
    )).scalars().all()
    return {
        "workspace": summary(t, users=usage["usage"]["current_users"], last_sale=last_sale,
                             until=await paid_until(db, t.id), lic=lic, installs=list(installs)),
        "installations": [installation_out(i) for i in installs],
        "quotas": usage["quotas"],
        "is_read_only": usage["is_read_only"],
        "invoices": [invoice_out(i, t) for i in invoices if i.status != "cancelled"],
    }


@router.post("/{tenant_id}/open")
async def open_workspace(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    """An ERP session for the owner's user in this workspace, handed to the app."""
    t = await owned_workspace(db, owner, tenant_id)
    if t.status == "suspended":
        raise HTTPException(status_code=403, detail="مساحة العمل هذه موقوفة من إدارة ميزان. تواصل مع الدعم لإعادة تفعيلها.")
    if is_on_premise(t):
        raise HTTPException(status_code=409, detail="مساحة العمل هذه تعمل على أجهزتك. نزّل البرنامج من زر «تنزيل».")
    user = await workspace_user(db, owner, t)
    if not user:
        raise HTTPException(status_code=404, detail="لا يوجد حساب مدير نشط في مساحة العمل هذه")
    if user.owner_account_id is None:
        user.owner_account_id = owner.id
        await db.commit()
    return {"access_token": auth_service.issue_token(user)["access_token"], "slug": t.slug, "username": user.username}


def installation_out(i: Installation) -> dict:
    return {
        "id": str(i.id),
        "mode": i.mode,
        "hostname": i.hostname,
        "os": i.os,
        "app_version": i.app_version,
        "first_seen_at": iso(i.first_seen_at),
        "last_seen_at": iso(i.last_seen_at),
        "last_backup_at": iso(i.last_backup_at),
    }


@router.get("/{tenant_id}/download")
async def download(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    """What a single-device/LAN workspace needs to be installed: its licence key
    (fresh, with the current end date) and the installers published for it."""
    t = await owned_workspace(db, owner, tenant_id)
    if not is_on_premise(t):
        raise HTTPException(status_code=409, detail="مساحة العمل هذه تعمل على السحابة، ولا تحتاج تنزيلًا.")
    try:
        key, lic = await issue_key(db, t)
    except LicenceError as e:
        raise HTTPException(status_code=503, detail="تعذر إصدار مفتاح الترخيص الآن. حاول لاحقًا.") from e
    await db.commit()
    return {
        "licence_key": key,
        "valid_until": iso(lic.valid_until),
        "status": licence_status(lic),
        "mode": t.deployment_mode,
        "installers": published_installers(t.deployment_mode),
    }

"""The owner's workspaces: list, create, details and opening one in the app."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import get_plan
from app.core.sectors import SECTORS
from app.db.base import get_db
from app.models.billing import BillingInvoice
from app.models.owner import OwnerAccount
from app.models.sale import Sale
from app.models.tenant import Tenant
from app.models.user import User
from app.services import auth_service
from app.services.owners import get_current_owner, owned_workspace, workspace_user
from app.services.plan_gating import get_tenant_limits_and_usage
from app.services.subscriptions import paid_until
from app.services.workspaces import create_workspace
from owner_api.common import days_until, invoice_out, iso

router = APIRouter(prefix="/account/workspaces", tags=["workspaces"])

MAX_WORKSPACES = 10
MAX_TRIALS = 3


def summary(t: Tenant, *, users: int = 0, last_sale: datetime | None = None, until: datetime | None = None) -> dict:
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
        "paid_until": iso(until),
        "users_count": users,
        "last_sale_at": iso(last_sale),
        "created_at": iso(t.created_at),
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
    return {"items": [summary(t, users=users.get(t.id, 0), last_sale=last_sale.get(t.id), until=until.get(t.id)) for t in tenants]}


class NewWorkspace(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    sector: str
    scale: Literal["small", "medium", "large"] = "small"
    demo_data: bool = True


@router.post("", status_code=201)
async def new_workspace(data: NewWorkspace, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
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
    tenant, _ = await create_workspace(
        db, name=data.name, sector=data.sector, scale=data.scale, demo_data=data.demo_data, owner=owner,
        admin_username=owner.login, admin_full_name=owner.full_name, admin_password_hash=owner.password_hash,
    )
    await db.commit()
    return summary(tenant, users=1)


@router.get("/{tenant_id}")
async def workspace_detail(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    t = await owned_workspace(db, owner, tenant_id)
    usage = await get_tenant_limits_and_usage(db, t.id)
    invoices = (await db.execute(
        select(BillingInvoice).where(BillingInvoice.tenant_id == t.id).order_by(BillingInvoice.created_at.desc()).limit(50)
    )).scalars().all()
    last_sale = await db.scalar(select(func.max(Sale.created_at)).where(Sale.tenant_id == t.id))
    return {
        "workspace": summary(t, users=usage["usage"]["current_users"], last_sale=last_sale, until=await paid_until(db, t.id)),
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
    user = await workspace_user(db, owner, t)
    if not user:
        raise HTTPException(status_code=404, detail="لا يوجد حساب مدير نشط في مساحة العمل هذه")
    if user.owner_account_id is None:
        user.owner_account_id = owner.id
        await db.commit()
    return {"access_token": auth_service.issue_token(user)["access_token"], "slug": t.slug, "username": user.username}

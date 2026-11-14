"""Owner accounts (#73): who owns which workspaces, and the support actions on them.

ADR-004 created one owner account per workspace when it backfilled, so a person who owned two
workspaces before may have two accounts: "merge" moves one account's workspaces into the other.
Every action is recorded in the audit log.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import iso, record
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.auth.services.owners import bypass_rls
from app.platform.billing.models import BillingInvoice
from app.platform.tenancy.models import Tenant

router = APIRouter(prefix="/admoon/owners", tags=["admin: owners"])


async def _get(db: AsyncSession, owner_id: uuid.UUID) -> OwnerAccount:
    owner = await db.get(OwnerAccount, owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Owner account not found")
    return owner


def _out(o: OwnerAccount, workspaces: list[Tenant] | None = None, paid_egp: float = 0.0, count: int | None = None) -> dict:
    return {
        "id": str(o.id), "login": o.login, "full_name": o.full_name, "email": o.email, "email_verified": bool(o.email and o.email_verified_at), "phone": o.phone,
        "is_active": o.is_active, "last_login_at": iso(o.last_login_at), "created_at": iso(o.created_at),
        "workspace_count": count if count is not None else len(workspaces or []),
        "paid_egp": round(paid_egp, 2),
        **({"workspaces": [{"id": str(t.id), "name": t.name, "slug": t.slug, "plan": t.plan, "status": t.status,
                            "deployment_mode": t.deployment_mode} for t in workspaces]} if workspaces is not None else {}),
    }


@router.get("")
async def list_owners(q: str | None = None, without_workspaces: bool = False,
                      db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    counts = (select(Tenant.owner_account_id.label("oid"), func.count(Tenant.id).label("n"))
              .group_by(Tenant.owner_account_id).subquery())
    paid = (select(Tenant.owner_account_id.label("oid"), func.coalesce(func.sum(BillingInvoice.amount_egp), 0).label("egp"))
            .join(BillingInvoice, BillingInvoice.tenant_id == Tenant.id).where(BillingInvoice.status == "paid")
            .group_by(Tenant.owner_account_id).subquery())
    stmt = (select(OwnerAccount, func.coalesce(counts.c.n, 0), func.coalesce(paid.c.egp, 0))
            .outerjoin(counts, counts.c.oid == OwnerAccount.id).outerjoin(paid, paid.c.oid == OwnerAccount.id)
            .order_by(OwnerAccount.created_at.desc()).limit(500))
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(OwnerAccount.login).like(like), func.lower(OwnerAccount.full_name).like(like),
                              func.lower(func.coalesce(OwnerAccount.email, "")).like(like),
                              func.coalesce(OwnerAccount.phone, "").like(like)))
    if without_workspaces:
        stmt = stmt.where(func.coalesce(counts.c.n, 0) == 0)
    rows = (await db.execute(stmt)).all()
    return {"items": [_out(o, count=n, paid_egp=float(egp)) for o, n, egp in rows]}


@router.get("/{owner_id}")
async def owner_detail(owner_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    o = await _get(db, owner_id)
    workspaces = (await db.execute(select(Tenant).where(Tenant.owner_account_id == o.id).order_by(Tenant.created_at))).scalars().all()
    paid = await db.scalar(select(func.coalesce(func.sum(BillingInvoice.amount_egp), 0))
                           .where(BillingInvoice.tenant_id.in_([t.id for t in workspaces] or [uuid.uuid4()]),
                                  BillingInvoice.status == "paid"))
    return _out(o, list(workspaces), float(paid or 0))


@router.post("/{owner_id}/reset-password")
async def reset_password(owner_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                         admin: User = Depends(require_superadmin)):
    """A new temporary password, shown once; every session of the owner ends, and the owner's
    workspace logins take the same password (as when the owner changes it)."""
    from app.platform.auth.services.owner_mail import set_owner_password

    o = await _get(db, owner_id)
    password = "Mz-" + secrets.token_urlsafe(9)
    changed = await set_owner_password(db, o, hash_password(password))
    await db.commit()
    await record(db, admin, "owner_password_reset", request=request, owner=o.login, workspace_logins=changed)
    return {"password": password, "workspace_logins_updated": changed}


@router.post("/{owner_id}/send-reset-code")
async def send_reset_code(owner_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                          admin: User = Depends(require_superadmin)):
    """Email the owner a code to choose a new password themselves (#71): only to a verified address."""
    from app.platform.auth.services import owner_mail

    o = await _get(db, owner_id)
    if not (o.email and o.email_verified_at):
        raise HTTPException(409, "This owner has no verified email. Set a temporary password instead.")
    await owner_mail.send_code(db, o, "reset_password", o.email)
    await record(db, admin, "owner_reset_code_sent", request=request, owner=o.login)
    return {"sent_to": owner_mail.mask(o.email)}


class Active(BaseModel):
    active: bool


@router.post("/{owner_id}/active")
async def set_active(owner_id: uuid.UUID, body: Active, request: Request, db: AsyncSession = Depends(get_db),
                     admin: User = Depends(require_superadmin)):
    """Disable or enable an owner account. Disabling refuses their sign-in and ends their sessions,
    and does the same for their own logins in their workspaces (otherwise they'd still run them as
    admin); the workspaces keep running for their staff. Enabling turns back on only the logins
    this disabled."""
    o = await _get(db, owner_id)
    now = datetime.now(UTC)
    settings_ = dict(o.settings or {})
    if not body.active and o.is_active:
        await bypass_rls(db)
        ids = (await db.execute(select(User.id).where(User.owner_account_id == o.id, User.is_active.is_(True)))).scalars().all()
        if ids:
            await db.execute(update(User).where(User.id.in_(ids)).values(is_active=False, tokens_valid_after=now))
        settings_["disabled_logins"] = [str(i) for i in ids]
        o.tokens_valid_after = now
    elif body.active and not o.is_active:
        ids = [uuid.UUID(i) for i in settings_.pop("disabled_logins", [])]
        if ids:
            await bypass_rls(db)
            await db.execute(update(User).where(User.id.in_(ids)).values(is_active=True))
    o.is_active, o.settings = body.active, settings_
    await db.commit()
    await record(db, admin, "owner_enabled" if body.active else "owner_disabled", request=request, owner=o.login)
    return _out(o, count=await db.scalar(select(func.count()).select_from(Tenant).where(Tenant.owner_account_id == o.id)))


class MoveWorkspace(BaseModel):
    tenant_id: uuid.UUID


@router.post("/{owner_id}/workspaces")
async def move_workspace(owner_id: uuid.UUID, body: MoveWorkspace, request: Request, db: AsyncSession = Depends(get_db),
                         admin: User = Depends(require_superadmin)):
    """Give a workspace to this owner. The previous owner's link to their user in it is removed,
    so the new owner opens it as its first admin."""
    o = await _get(db, owner_id)
    t = await db.get(Tenant, body.tenant_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if t.owner_account_id == o.id:
        raise HTTPException(status_code=409, detail="This owner already owns the workspace")
    previous = await db.get(OwnerAccount, t.owner_account_id) if t.owner_account_id else None
    await db.execute(update(User).where(User.tenant_id == t.id, User.owner_account_id.is_not(None)).values(owner_account_id=None))
    t.owner_account_id = o.id
    await db.commit()
    await record(db, admin, "workspace_owner_changed", tenant_id=t.id, request=request,
                 workspace_name=t.name, owner=o.login, previous_owner=previous.login if previous else None)
    return await owner_detail(owner_id, db, admin)


class Merge(BaseModel):
    into: uuid.UUID


@router.post("/{owner_id}/merge")
async def merge(owner_id: uuid.UUID, body: Merge, request: Request, db: AsyncSession = Depends(get_db),
                admin: User = Depends(require_superadmin)):
    """Move every workspace of this owner account into another, then delete this one. Their
    users keep their link, now to the other account."""
    if owner_id == body.into:
        raise HTTPException(status_code=400, detail="Choose another owner account")
    source, target = await _get(db, owner_id), await _get(db, body.into)
    moved = (await db.execute(update(Tenant).where(Tenant.owner_account_id == source.id)
                              .values(owner_account_id=target.id).returning(Tenant.id))).scalars().all()
    await db.execute(update(User).where(User.owner_account_id == source.id).values(owner_account_id=target.id))
    login = source.login
    await db.delete(source)
    await db.commit()
    await record(db, admin, "owners_merged", request=request, owner=target.login, merged=login, workspaces=len(moved))
    return await owner_detail(target.id, db, admin)


@router.delete("/{owner_id}", status_code=204)
async def delete_owner(owner_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                       admin: User = Depends(require_superadmin)):
    """Delete an owner account left with no workspaces."""
    o = await _get(db, owner_id)
    if await db.scalar(select(func.count()).select_from(Tenant).where(Tenant.owner_account_id == o.id)):
        raise HTTPException(status_code=409, detail="This owner still has workspaces: move or delete them first")
    login = o.login
    await db.execute(update(User).where(User.owner_account_id == o.id).values(owner_account_id=None))
    await db.delete(o)
    await db.commit()
    await record(db, admin, "owner_deleted", request=request, owner=login)

"""Owner accounts: sign-in to the owner panel and the link to workspaces.

Where someone signs in decides who they are:
- a workspace's login page (the ERP)  → an ERP user of that one workspace;
- the Mizan platform (the owner panel) → an owner account, across all the
  workspaces it owns.
Owner tokens carry `scope: owner` and are refused by the ERP; ERP tokens are
refused by the owner API.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.auth.security import create_access_token, decode_token, verify_password
from app.db.base import get_db
from app.platform.auth.models.owner import OwnerAccount
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User

OWNER_SCOPE = "owner"
_bearer = OAuth2PasswordBearer(tokenUrl="/account/login", auto_error=False)


def normalize_login(value: str) -> str:
    return value.strip().lower()


async def bypass_rls(db: AsyncSession) -> None:
    """Owner reads span the owner's workspaces; every query filters by owner.
    Transaction-local: call again after a commit."""
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))


async def authenticate_owner(db: AsyncSession, login: str, password: str) -> OwnerAccount:
    owner = await db.scalar(select(OwnerAccount).where(OwnerAccount.login == normalize_login(login)))
    if not owner or not owner.is_active or not verify_password(password, owner.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="اسم الدخول أو كلمة المرور غير صحيحة")
    owner.last_login_at = datetime.now(UTC)
    return owner


def issue_owner_token(owner: OwnerAccount) -> str:
    return create_access_token({"sub": str(owner.id), "scope": OWNER_SCOPE})


async def get_current_owner(token: str | None = Depends(_bearer), db: AsyncSession = Depends(get_db)) -> OwnerAccount:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(token)
    if payload.get("scope") != OWNER_SCOPE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="هذا الحساب ليس حساب مالك")
    try:
        owner_id = uuid.UUID(str(payload.get("sub")))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None
    owner = await db.get(OwnerAccount, owner_id)
    if not owner or not owner.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    from app.platform.auth.sessions import ensure_live

    await ensure_live(db, payload, owner.tokens_valid_after)  # #77
    await bypass_rls(db)
    owner.token_payload = payload  # for sign-out
    return owner


async def owned_workspace(db: AsyncSession, owner: OwnerAccount, tenant_id: uuid.UUID) -> Tenant:
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.owner_account_id == owner.id))
    if not tenant:
        raise HTTPException(status_code=404, detail="مساحة العمل غير موجودة")
    return tenant


async def workspace_user(db: AsyncSession, owner: OwnerAccount, tenant: Tenant) -> User | None:
    """The ERP user the owner signs in as: the one linked to the owner account,
    else the workspace's first active admin."""
    return await db.scalar(
        select(User)
        .where(User.tenant_id == tenant.id, User.is_active.is_(True), User.is_superadmin.is_(False))
        .order_by((User.owner_account_id == owner.id).desc().nulls_last(), (User.role == "admin").desc(), User.created_at)
        .limit(1)
    )


async def unique_login(db: AsyncSession, wanted: str) -> str:
    base = normalize_login(wanted)
    candidate, n = base, 1
    while await db.scalar(select(OwnerAccount.id).where(OwnerAccount.login == candidate)):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


async def create_owner_for(db: AsyncSession, user: User, *, phone: str | None = None, email: str | None = None) -> OwnerAccount:
    """An owner account for a new workspace's first admin, with the same login and
    password, linked to the workspace and that user. The caller commits."""
    owner = OwnerAccount(
        id=uuid.uuid4(),
        login=await unique_login(db, user.username),
        full_name=user.full_name,
        phone=phone,
        email=email,
        password_hash=user.password_hash,
    )
    db.add(owner)
    await db.flush()
    user.owner_account_id = owner.id
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant:
        tenant.owner_account_id = owner.id
    return owner

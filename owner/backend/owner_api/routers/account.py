"""Owner sign-in and profile."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.core.security import hash_password, verify_password
from app.db.base import get_db
from app.models.owner import OwnerAccount
from app.models.user import User
from app.services.owners import authenticate_owner, bypass_rls, get_current_owner, issue_owner_token

router = APIRouter(prefix="/account", tags=["account"])

login_limiter = RateLimiter(max_requests=10, window_seconds=60)


def profile(o: OwnerAccount) -> dict:
    return {
        "id": str(o.id),
        "login": o.login,
        "full_name": o.full_name,
        "email": o.email,
        "phone": o.phone,
        "tour_done": bool((o.settings or {}).get("tour_done_at")),
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db), _=Depends(login_limiter)):
    owner = await authenticate_owner(db, data.login, data.password)
    await db.commit()
    # Bearer only: the panel keeps the token itself; no cookie session.
    return {"access_token": issue_owner_token(owner), "owner": profile(owner)}


@router.get("/me")
async def me(owner: OwnerAccount = Depends(get_current_owner)):
    return profile(owner)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=128)
    email: str | None = Field(default=None, max_length=254, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=32, pattern=r"^$|^[0-9+ ]{6,32}$")


@router.patch("/me")
async def update_me(data: ProfileUpdate, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    if data.full_name is not None:
        owner.full_name = data.full_name.strip()
    if data.email is not None:
        owner.email = data.email.strip() or None
    if data.phone is not None:
        owner.phone = data.phone.strip() or None
    await db.commit()
    return profile(owner)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/password")
async def change_password(data: PasswordChange, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    if not verify_password(data.current_password, owner.password_hash):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    owner.password_hash = hash_password(data.new_password)
    # The owner signs in to each workspace with the same password.
    await bypass_rls(db)
    changed = await db.execute(update(User).where(User.owner_account_id == owner.id).values(password_hash=owner.password_hash))
    await db.commit()
    return {"ok": True, "workspace_logins_updated": changed.rowcount}


@router.post("/tour-done")
async def tour_done(db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    owner.settings = {**(owner.settings or {}), "tour_done_at": datetime.now(UTC).isoformat()}
    await db.commit()
    return profile(owner)

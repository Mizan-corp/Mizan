"""The owner's profile. Owners sign in on the app's /login (app.platform.auth.routes.owner_login)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.auth.security import hash_password, verify_password
from app.db.base import get_db
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.models.user import User
from app.platform.auth.services.owners import bypass_rls, get_current_owner, issue_owner_token

router = APIRouter(prefix="/account", tags=["account"])

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
    from app.platform.auth.sessions import sessions_end_now

    ended = sessions_end_now()
    owner.password_hash = hash_password(data.new_password)
    owner.tokens_valid_after = ended  # every other session ends (#77)
    # The owner signs in to each workspace with the same password; those sessions end too.
    await bypass_rls(db)
    changed = await db.execute(update(User).where(User.owner_account_id == owner.id)
                               .values(password_hash=owner.password_hash, tokens_valid_after=ended))
    await db.commit()
    return {"ok": True, "workspace_logins_updated": changed.rowcount, "access_token": issue_owner_token(owner)}


@router.post("/logout", status_code=204)
async def logout(db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    """Sign this session out on the server (#77). The website's copy of the token ends with it."""
    from app.platform.auth.sessions import revoke

    await revoke(db, owner.token_payload)
    await db.commit()


@router.post("/tour-done")
async def tour_done(db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    owner.settings = {**(owner.settings or {}), "tour_done_at": datetime.now(UTC).isoformat()}
    await db.commit()
    return profile(owner)

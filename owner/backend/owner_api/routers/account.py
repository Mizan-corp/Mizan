"""The owner's profile. Owners sign in on the app's /login (app.platform.auth.routes.owner_login)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.auth.security import hash_password, verify_password
from app.db.base import get_db
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.services.owners import get_current_owner, issue_owner_token

router = APIRouter(prefix="/account", tags=["account"])


def email_enabled() -> bool:
    from app.platform.notifications.service import email_enabled as enabled

    return enabled()

def profile(o: OwnerAccount) -> dict:
    return {
        "id": str(o.id),
        "login": o.login,
        "full_name": o.full_name,
        "email": o.email,
        "email_verified": bool(o.email and o.email_verified_at),
        "email_service": email_enabled(),
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
        new = data.email.strip().lower() or None
        if new != (owner.email or "").lower() or None:
            owner.email, owner.email_verified_at = new, None  # a new address needs proving again
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
    from app.platform.auth.services.owner_mail import set_owner_password

    # Every other session ends (#77); the workspaces' logins take the same password.
    changed = await set_owner_password(db, owner, hash_password(data.new_password))
    await db.commit()
    return {"ok": True, "workspace_logins_updated": changed, "access_token": issue_owner_token(owner)}


# ── Verifying the email (#72) ───────────────────────────────────────────────────

@router.post("/email/send-code")
async def send_email_code(db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    """Email a code to the account's address, to prove it."""
    from app.platform.auth.services import owner_mail

    if not owner.email:
        raise HTTPException(status_code=422, detail="أضف بريدك الإلكتروني أولًا")
    if owner.email_verified_at:
        return {"ok": True, "already": True}
    await owner_mail.send_code(db, owner, "verify_email", owner.email)
    return {"ok": True, "to": owner_mail.mask(owner.email)}


class EmailCode(BaseModel):
    code: str = Field(min_length=6, max_length=12)


@router.post("/email/verify")
async def verify_email(data: EmailCode, db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    from app.platform.auth.services import owner_mail

    from sqlalchemy import func, select

    row = await owner_mail.check_code(db, owner, "verify_email", data.code)
    if (row.email or "").lower() != (owner.email or "").lower():
        raise HTTPException(status_code=409, detail="تغيّر بريدك بعد إرسال الرمز؛ اطلب رمزًا جديدًا.")
    # One verified owner per address: it is how a forgotten password is reset (#71).
    if await db.scalar(select(OwnerAccount.id).where(func.lower(OwnerAccount.email) == owner.email.lower(),
                                                     OwnerAccount.email_verified_at.is_not(None), OwnerAccount.id != owner.id).limit(1)):
        raise HTTPException(status_code=409, detail="هذا البريد مؤكَّد لحساب آخر على ميزان؛ استخدم بريدًا غيره.")
    owner.email_verified_at = datetime.now(UTC)
    await db.commit()
    return profile(owner)


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

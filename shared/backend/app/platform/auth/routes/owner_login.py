"""Owner sign-in, served by the ERP API for its /login page.

The app's /login (no workspace in the address) is where owners sign in; it hands
the owner session to the owner panel. Employees sign in on their workspace's
page (/c/<workspace>/login). If an employee's username and password are typed
here, the answer points them to that page instead of signing them in.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.db.base import get_db
from app.platform.tenancy.models import Tenant
from app.platform.auth.services import auth as auth_service
from app.platform.auth.services.owners import authenticate_owner, issue_owner_token

router = APIRouter(prefix="/account", tags=["owner sign-in"])

login_limiter = RateLimiter(max_requests=10, window_seconds=60)


class OwnerLogin(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
async def owner_login(data: OwnerLogin, db: AsyncSession = Depends(get_db), _=Depends(login_limiter)):
    try:
        owner = await authenticate_owner(db, data.login, data.password)
    except HTTPException as owner_error:
        # Not an owner: an employee with the right password learns where to sign in.
        try:
            user = await auth_service.authenticate(db, data.login.strip(), data.password)
        except HTTPException:
            raise owner_error from None
        if user.is_superadmin:
            # Platform staff sign in on the admin panel (#78).
            return {"admin_panel": True}
        slug = await db.scalar(select(Tenant.slug).where(Tenant.id == user.tenant_id))
        if not slug:
            raise owner_error from None
        return {"employee_workspace": slug}
    await db.commit()
    # No cookie: the token is handed to the owner panel, which keeps it itself.
    return {"access_token": issue_owner_token(owner)}


# ── Forgot password (#71): a code to the account's verified email, then a new password ───────

reset_limiter = RateLimiter(max_requests=5, window_seconds=900)


class ForgotPassword(BaseModel):
    login: str = Field(min_length=2, max_length=254)


@router.post("/password/forgot")
async def forgot_password(data: ForgotPassword, db: AsyncSession = Depends(get_db), _=Depends(reset_limiter)):
    """Email a reset code if the account has a verified address. The answer is the same either
    way, so it doesn't reveal which accounts exist."""
    from app.platform.auth.services import owner_mail

    owner_mail.require_email_service()
    owner = await owner_mail.find_for_reset(db, data.login)
    if owner is not None and owner.email and owner.email_verified_at:
        try:
            await owner_mail.send_code(db, owner, "reset_password", owner.email)
        except HTTPException as e:
            if e.status_code != 429:  # too soon / too many: answer as if sent
                raise
    return {"ok": True, "detail": "إن كان الحساب مرتبطًا ببريد مؤكَّد فقد أرسلنا إليه رمزًا صالحًا 15 دقيقة."}


class ResetPassword(BaseModel):
    login: str = Field(min_length=2, max_length=254)
    code: str = Field(min_length=6, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/password/reset")
async def reset_password(data: ResetPassword, db: AsyncSession = Depends(get_db), _=Depends(reset_limiter)):
    """Set a new password with the emailed code; every session ends and the owner is signed in."""
    from app.platform.auth.security import hash_password
    from app.platform.auth.services import owner_mail

    owner = await owner_mail.find_for_reset(db, data.login)
    if owner is None:
        raise HTTPException(400, "الرمز غير صحيح أو انتهت صلاحيته؛ اطلب رمزًا جديدًا إن لزم.")
    await owner_mail.check_code(db, owner, "reset_password", data.code)
    await owner_mail.set_owner_password(db, owner, hash_password(data.new_password))
    await db.commit()
    return {"access_token": issue_owner_token(owner)}

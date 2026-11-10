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
from app.models.tenant import Tenant
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

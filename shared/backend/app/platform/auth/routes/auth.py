import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import RateLimiter
from app.platform.auth.security import create_access_token
from app.db.base import get_db
from app.dependencies import ensure_workspace_open, get_current_user
from app.platform.auth.models.user import User
from app.platform.auth.schemas.auth import LoginRequest, TokenResponse
from app.platform.auth.schemas.user import UserPasswordUpdate
from app.platform.auth.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

login_limiter = RateLimiter(max_requests=10, window_seconds=60)
password_limiter = RateLimiter(max_requests=3, window_seconds=300)
reauth_limiter = RateLimiter(max_requests=5, window_seconds=60)


@router.post("/login")
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db), _=Depends(login_limiter)):
    user = await auth_service.authenticate(db, data.username, data.password, tenant_slug=data.tenant_slug)
    await ensure_workspace_open(db, user)
    token = auth_service.issue_token(user)
    body = TokenResponse(
        access_token=token["access_token"],
        token_type="bearer",
        user_id=token["user_id"],
        username=token["username"],
        full_name=token["full_name"],
        role=token["role"],
    ).model_dump()
    resp = JSONResponse(content=body)
    resp.set_cookie(
        key="access_token",
        value=token["access_token"],
        httponly=True,
        secure=settings.IS_PRODUCTION,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return resp


@router.get("/roles")
async def get_roles(_=Depends(get_current_user)):
    from app.platform.permissions.roles import ROLE_LABELS
    return [{"value": k, "label": v} for k, v in ROLE_LABELS.items()]


@router.get("/me")
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.platform.tenancy.models import Tenant
    user = await db.merge(current_user)
    await db.refresh(user)

    tenant_info = None
    if user.tenant_id:
        t = await db.get(Tenant, user.tenant_id)
        if t:
            if not t.slug:
                t.slug = f"tenant-{str(t.id)[:8]}"
                await db.commit()
            tenant_info = {
                "id": str(t.id),
                "name": t.name,
                "slug": t.slug,
                "custom_domain": t.custom_domain,
                "sector": t.sector,
                "business_type": t.business_type,
                "palette": t.palette or {"name": "neutral", "hue": 0},
                "active_modules": t.active_modules or ["pos", "inventory"],
                "deployment_mode": t.deployment_mode,
                "tech_stack": t.tech_stack or {},
                "limits": t.limits or {},
                "plan": t.plan,
                "trial_ends_at": t.trial_ends_at.isoformat() if t.trial_ends_at else None,
                "paid_until": t.paid_until.isoformat() if t.paid_until else None,
            }

    # The acting role's permissions (ADR-006 phase 3): no "*", even for admins.
    perms = sorted(getattr(current_user, "effective_permissions", frozenset()))
    acting = getattr(current_user, "acting_role", None)
    roles = [{"id": str(r["id"]), "code": r["code"], "name": r["name"]} for r in getattr(current_user, "assigned_roles", [])]

    return {
        "id": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "permissions": perms,
        "acting_role": {"id": str(acting["id"]), "code": acting["code"], "name": acting["name"]} if acting else None,
        "roles": roles,
        "is_manager": bool(user.is_manager) if user.is_manager is not None else False,
        "is_superadmin": bool(user.is_superadmin),
        "default_warehouse_id": str(user.default_warehouse_id) if user.default_warehouse_id else None,
        "tenant": tenant_info,
    }


def _session_cookie(resp: JSONResponse, token: str) -> JSONResponse:
    resp.set_cookie(key="access_token", value=token, httponly=True, secure=settings.IS_PRODUCTION,
                    samesite="lax", max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/")
    return resp


@router.put("/me/password")
async def change_password(data: UserPasswordUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), _=Depends(password_limiter)):
    """Ends every other session (#77) and returns a fresh token for this one."""
    if current_user.owner_account_id:
        from fastapi import HTTPException

        # One password for the owner everywhere: it is changed in the owner panel (#75).
        raise HTTPException(409, "كلمة مرور حساب المالك تُغيَّر من لوحة المالك")
    from app.platform.auth.sessions import sessions_end_now

    user = await db.merge(current_user)
    user.tokens_valid_after = sessions_end_now()
    await auth_service.change_password(db, user, data.current_password, data.new_password)
    token = auth_service.issue_token(user)["access_token"]
    return _session_cookie(JSONResponse({"detail": "Password updated", "access_token": token}), token)


@router.post("/logout", status_code=204)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Sign this session out on the server too (#77): its token is refused from now on."""
    from fastapi import Response

    from app.platform.auth.security import decode_token
    from app.platform.auth.sessions import revoke

    auth = request.headers.get("authorization", "")
    for raw in (auth[7:] if auth.lower().startswith("bearer ") else None, request.cookies.get("access_token")):
        if not raw:
            continue
        try:
            await revoke(db, decode_token(raw))
        except Exception:
            continue  # an invalid or expired token is already signed out
    await db.commit()
    resp = Response(status_code=204)
    resp.delete_cookie("access_token", path="/")
    return resp


@router.post("/print-token")
async def issue_print_token(current_user: User = Depends(get_current_user)):
    token = create_access_token(
        {"sub": str(current_user.id), "scope": "print", "tid": str(current_user.tenant_id)},
        expires_delta=timedelta(seconds=60),
    )
    return {"token": token}


@router.post("/reauthenticate")
async def reauthenticate(data: LoginRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), _=Depends(reauth_limiter)):
    """Verify credentials without issuing a new session — used for handover/manager approval."""
    user = await auth_service.authenticate(db, data.username, data.password)
    return {"user_id": str(user.id), "username": user.username, "full_name": user.full_name}


class ActingRoleIn(BaseModel):
    role_id: uuid.UUID


@router.post("/me/acting-role")
async def switch_acting_role(data: ActingRoleIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Act as another of one's assigned roles. Nobody holds every permission at once (#94)."""
    from app.platform.permissions.access import switch_role

    role = await switch_role(db, current_user, data.role_id)
    await db.commit()
    return {"acting_role": {"id": str(role["id"]), "code": role["code"], "name": role["name"]},
            "permissions": sorted(current_user.effective_permissions)}

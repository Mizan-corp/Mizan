import uuid
from datetime import datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.auth.security import decode_token
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.db.base import get_db
from app.platform.auth.models.user import User, user_warehouses

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _decode_user_id(payload: dict) -> str:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return user_id


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # An explicit Bearer token wins over the cookie: a session handed over from
    # the owner or admin panel must not be overridden by an older sign-in's
    # cookie in the same browser.
    payload = None
    if token:
        try:
            payload = decode_token(token)
        except HTTPException:
            payload = None

    cookie_token = request.cookies.get("access_token")
    if not payload and cookie_token:
        try:
            payload = decode_token(cookie_token)
        except HTTPException:
            payload = None

    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if payload.get("scope") == "owner":
        # Owner-panel sessions don't open the ERP; the panel hands over an ERP token.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = _decode_user_id(payload)
    tid_str = payload.get("tid")
    if tid_str:
        await bind_tenant(db, uuid.UUID(tid_str))
    else:
        # Fallback for tokens issued without tid payload
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.is_active)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    from app.platform.auth.sessions import ensure_live

    await ensure_live(db, payload, user.tokens_valid_after)  # signed out, or sessions ended (#77)
    if not tid_str:
        await bind_tenant(db, user.tenant_id)
    await ensure_workspace_open(db, user)
    from app.platform.permissions.access import load_acting

    await load_acting(db, user)  # the role the user acts as, and its permissions
    return user


SUSPENDED_DETAIL = "تم إيقاف مساحة العمل هذه مؤقتًا من إدارة منصة ميزان. تواصل مع الدعم لإعادة تفعيلها."


async def ensure_workspace_open(db: AsyncSession, user: User) -> None:
    """Suspended workspaces are closed to their own people; platform staff keep access."""
    if user.is_superadmin or user.role == "superadmin" or not user.tenant_id:
        return
    from app.platform.tenancy.models import Tenant

    workspace_status = await db.scalar(select(Tenant.status).where(Tenant.id == user.tenant_id))
    if workspace_status == "suspended":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SUSPENDED_DETAIL)


async def get_print_user(request: Request, token: str | None = None, db: AsyncSession = Depends(get_db)) -> User:
    # The print token in the URL first (the browser's session cookie is not a print token).
    t = token or request.cookies.get("access_token")
    if not t:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    payload = decode_token(t)
    # Validate print scope
    if payload.get("scope") != "print":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token scope for print")
    user_id = payload.get("sub")
    tid_str = payload.get("tid")
    if tid_str:
        await bind_tenant(db, uuid.UUID(tid_str))
    else:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id), User.is_active))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    from app.platform.auth.sessions import ensure_live

    await ensure_live(db, payload, user.tokens_valid_after)
    if not tid_str:
        await bind_tenant(db, user.tenant_id)
    from app.platform.permissions.access import load_acting

    await load_acting(db, user)  # the role the user acts as, and its permissions
    return user


def require_perm(*perms: str):
    """Any of `perms` held by the role the user acts as now. No "*", no role-name bypass (#94)."""
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        from app.platform.permissions.access import can

        if can(current_user, *perms):
            return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return checker


async def require_is_manager(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="مدير فقط")
    return current_user


async def require_open_period(db: AsyncSession = Depends(get_db)):
    """Block transactions if the current accounting month is closed.
    Uses the same table schema as periods.py (UUID pk, closed_by, closed_at).
    """
    month = datetime.now().strftime("%Y-%m")
    try:
        status_row = (await db.execute(text(
            "SELECT status FROM accounting_periods WHERE month=:m"
        ), {"m": month})).scalar_one_or_none()
    except Exception as e:
        # Only allow through if the table doesn't exist (42P01 = undefined_table in PG)
        # For all other errors (connection, auth, etc.) — fail closed
        if hasattr(e, 'orig') and getattr(e.orig, 'pgcode', None) == '42P01':
            return  # table doesn't exist yet — no periods are closed
        raise
    if status_row == "closed":
        raise HTTPException(status_code=400, detail=f"الشهر {month} مغلق — لا يمكن إجراء المعاملات")


async def verify_warehouse_access(
    db: AsyncSession,
    current_user: User,
    warehouse_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Check if user has access to a warehouse. Returns warehouse_id if valid."""
    if warehouse_id is None:
        return None
    # Managers, and roles that supervise every branch, reach all warehouses.
    from app.platform.permissions.access import can

    if current_user.is_manager or can(current_user, "supervise"):
        return warehouse_id
    result = await db.execute(
        select(user_warehouses.c.warehouse_id).where(
            user_warehouses.c.user_id == current_user.id,
            user_warehouses.c.warehouse_id == warehouse_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ليس لديك صلاحية الوصول إلى هذا الفرع")
    return warehouse_id


async def require_superadmin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Superadmin gate for the SaaS owner (admoon dashboard).
    Grants access to users with is_superadmin=True, role='superadmin', or username in DEFAULT_SUPERADMINS.
    Enables postgres RLS bypass so the superadmin can query cross-tenant statistics and manage all clients.
    """
    is_super = bool(
        getattr(current_user, "is_superadmin", False)
        or current_user.role == "superadmin"
    )
    if not is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="صلاحية إدارة المنصة (Superadmin) مطلوبة للوصول إلى أديمون",
        )
    # Bypass tenant isolation so admoon can inspect all client ERPs
    current_tenant_id.set(None)
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    return current_user




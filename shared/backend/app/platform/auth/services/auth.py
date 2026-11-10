from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.auth.security import create_access_token, hash_password, verify_password
from app.platform.auth.models.user import User


async def authenticate(db: AsyncSession, username: str, password: str, tenant_slug: str | None = None) -> User:
    from sqlalchemy import text
    from app.platform.tenancy.models import Tenant

    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))

    if tenant_slug:
        tenant_res = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = tenant_res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="اسم المنشأة أو بيانات الاعتماد غير صحيحة",
            )
        stmt = select(User).where(User.username == username, User.tenant_id == tenant.id, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return user

    # No tenant_slug provided:
    stmt = select(User).where(User.username == username, User.is_active == True)
    result = await db.execute(stmt)
    users = result.scalars().all()

    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # If multiple accounts have this username across different tenants:
    if len(users) > 1:
        # Check if there is an unambiguous superadmin whose password matches
        superadmins = [u for u in users if getattr(u, "is_superadmin", False) or u.role == "superadmin"]
        if len(superadmins) == 1 and verify_password(password, superadmins[0].password_hash):
            return superadmins[0]
        # Ambiguous regular tenant users: must require tenant_slug
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="اسم المستخدم مسجل في عدة منشآت. يرجى تحديد معرف المنشأة (tenant_slug) للمتابعة",
        )

    # Exactly one user found
    user = users[0]
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def issue_token(user: User) -> dict:
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "username": user.username,
        "tid": str(user.tenant_id) if user.tenant_id else None,
    })
    return {"access_token": token, "token_type": "bearer", "user_id": str(user.id),
            "username": user.username, "role": user.role, "full_name": user.full_name or user.username,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None}


async def create_user(db: AsyncSession, data) -> User:
    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError

    from app.platform.permissions.roles import ROLE_DEFAULT_PERMISSIONS
    from app.platform.tenancy.context import current_tenant_id, primary_tenant_id
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 8 أحرف على الأقل")
    tid = current_tenant_id.get() or await primary_tenant_id(db)
    user = User(
        username=data.username,
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.password),
        permissions=ROLE_DEFAULT_PERMISSIONS.get(data.role, []),
        tenant_id=tid,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        import traceback
        traceback.print_exc()
        err_msg = str(exc).lower()
        if "uq_users_tenant_username" in err_msg or "users_username_key" in err_msg or ("unique constraint" in err_msg and "username" in err_msg):
            raise HTTPException(400, f"اسم المستخدم '{data.username}' مستخدم بالفعل") from None
        raise
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str):
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 8 أحرف على الأقل")
    user.password_hash = hash_password(new_password)
    await db.commit()

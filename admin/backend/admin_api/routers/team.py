"""Platform team: who can sign in to the admin panel."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import iso, record, tenant_names
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.platform.tenancy.models import PlatformAuditLog
from app.platform.auth.models.user import User

router = APIRouter(prefix="/admoon/team", tags=["admin: team"])

IS_STAFF = or_(User.is_superadmin.is_(True), User.role == "superadmin")


async def _people(db: AsyncSession, users: list[User]) -> list[dict]:
    names = await tenant_names(db, {u.tenant_id for u in users})
    last = dict((await db.execute(
        select(PlatformAuditLog.platform_user_id, func.max(PlatformAuditLog.created_at))
        .where(PlatformAuditLog.platform_user_id.in_([u.id for u in users]))
        .group_by(PlatformAuditLog.platform_user_id)
    )).all()) if users else {}
    return [
        {"id": str(u.id), "username": u.username, "full_name": u.full_name, "is_active": u.is_active,
         "workspace": names.get(u.tenant_id), "created_at": iso(u.created_at), "last_action_at": iso(last.get(u.id)),
         "is_staff": bool(u.is_superadmin or u.role == "superadmin")}
        for u in users
    ]


@router.get("")
async def list_team(db: AsyncSession = Depends(get_db), me: User = Depends(require_superadmin)):
    staff = (await db.execute(select(User).where(IS_STAFF).order_by(User.created_at))).scalars().all()
    return {"items": await _people(db, list(staff)), "me": str(me.id)}


@router.get("/candidates")
async def find_people(
    q: str = Query(min_length=2),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    like = f"%{q.lower()}%"
    users = (await db.execute(
        select(User).where(or_(func.lower(User.username).like(like), func.lower(User.full_name).like(like)))
        .order_by(User.username).limit(10)
    )).scalars().all()
    return {"items": await _people(db, list(users))}


class Grant(BaseModel):
    user_id: uuid.UUID


@router.post("")
async def grant_access(body: Grant, request: Request, db: AsyncSession = Depends(get_db),
                       me: User = Depends(require_superadmin)):
    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_superadmin = True
    await db.commit()
    await record(db, me, "platform_access_granted", tenant_id=user.tenant_id, request=request, user=user.username)
    return {"ok": True}


@router.delete("/{user_id}")
async def revoke_access(user_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                        me: User = Depends(require_superadmin)):
    if user_id == me.id:
        raise HTTPException(status_code=409, detail="You can't remove your own access")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_superadmin = False
    if user.role == "superadmin":
        user.role = "admin"
    await db.commit()
    await record(db, me, "platform_access_revoked", tenant_id=user.tenant_id, request=request, user=user.username)
    return {"ok": True}

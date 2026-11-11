"""Roles and who holds them (ADR-006 phase 3): /authz/access/…, all with the 'users' permission."""
import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User
from app.platform.permissions import access

router = APIRouter(prefix="/access", tags=["roles and access"])  # under /authz


class RoleIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    grants: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    grants: list[str] | None = None


class UserRolesIn(BaseModel):
    role_ids: list[uuid.UUID] = Field(min_length=1)
    active_role_id: uuid.UUID | None = None


def _out(r: dict) -> dict:
    return {"id": str(r["id"]), "code": r["code"], "name": r["name"], "grants": sorted(r["grants"] or []),
            "standard": bool(r.get("standard", r.get("tenant_id") is None))}


@router.get("/permissions")
async def list_permissions(_=Depends(require_perm("users"))):
    return access.declared_permissions()


@router.get("/roles")
async def list_roles(db: AsyncSession = Depends(get_db), _=Depends(require_perm("users"))):
    return [_out(r) for r in await access.available_roles(db)]


def _check_grants(grants: list[str], user) -> list[str]:
    unknown = set(grants) - set(access.all_permissions())
    if unknown:
        raise HTTPException(400, f"صلاحيات غير معروفة: {', '.join(sorted(unknown))}")
    access.ensure_within(user, grants)
    return sorted(set(grants))


@router.post("/roles", status_code=201)
async def create_role(data: RoleIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("users"))):
    grants = _check_grants(data.grants, user)
    code = "ws-" + (re.sub(r"[^a-z0-9]+", "-", data.name.lower()).strip("-")[:40] or "role") + "-" + uuid.uuid4().hex[:6]
    row = (await db.execute(text("""
        INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants)
        VALUES (gen_random_uuid(), :t, :code, :name, :name, false, false, CAST(:g AS jsonb))
        RETURNING id, code, name, grants, tenant_id
    """), {"t": user.tenant_id, "code": code, "name": data.name.strip(), "g": json.dumps(grants)})).mappings().one()
    await db.commit()
    return _out(dict(row))


async def _workspace_role(db: AsyncSession, role_id: uuid.UUID) -> dict:
    row = (await db.execute(text("SELECT id, code, name, grants, tenant_id FROM sys_roles WHERE id = :id"),
                            {"id": role_id})).mappings().first()
    if not row:
        raise HTTPException(404, "الدور غير موجود")
    if row["tenant_id"] is None:
        raise HTTPException(403, "الأدوار القياسية لا تُعدَّل؛ أنشئ دورًا خاصًا بالمنشأة")
    return dict(row)


@router.put("/roles/{role_id}")
async def update_role(role_id: uuid.UUID, data: RoleUpdate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_perm("users"))):
    role = await _workspace_role(db, role_id)
    access.ensure_within(user, role["grants"] or [])  # can't take over a role above your own
    if data.grants is not None:
        role["grants"] = _check_grants(data.grants, user)
    if data.name is not None:
        role["name"] = data.name.strip()
    await db.execute(text("UPDATE sys_roles SET name = :n, grants = CAST(:g AS jsonb), updated_at = now() WHERE id = :id"),
                     {"n": role["name"], "g": json.dumps(role["grants"]), "id": role_id})
    await db.commit()
    return _out(role)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("users"))):
    role = await _workspace_role(db, role_id)
    access.ensure_within(user, role["grants"] or [])
    holders = await db.scalar(text("SELECT count(*) FROM user_role_assignments WHERE role_id = :id"), {"id": role_id})
    if holders:
        raise HTTPException(409, f"الدور مُسند إلى {holders} مستخدم؛ أزله منهم أولًا")
    await db.execute(text("DELETE FROM sys_roles WHERE id = :id"), {"id": role_id})
    await db.commit()


@router.get("/users/{user_id}/roles")
async def user_roles(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("users"))):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "المستخدم غير موجود")
    roles = await access.roles_of(db, user_id)
    return {"roles": [_out(r) for r in roles],
            "active_role_id": str(target.active_role_id) if target.active_role_id else None}


@router.put("/users/{user_id}/roles")
async def set_user_roles(user_id: uuid.UUID, data: UserRolesIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_perm("users"))):
    """The owner (or anyone with 'users') assigns roles; the user then acts as one at a time."""
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "المستخدم غير موجود")
    roles = {r["id"]: r for r in await access.available_roles(db)}
    if any(rid not in roles for rid in data.role_ids):
        raise HTTPException(404, "دور غير موجود")
    for rid in data.role_ids:
        access.ensure_within(user, roles[rid]["grants"] or [])
    await access.assign_roles(db, target, list(data.role_ids), data.active_role_id)
    from app.platform.audit.service import log as audit_log

    await audit_log(db, "user", "assign_roles", user.id, user.full_name, user_id,
                    {"roles": [roles[rid]["code"] for rid in data.role_ids]}, "تعيين الأدوار")
    await db.commit()
    return {"roles": [_out(roles[rid]) for rid in data.role_ids]}

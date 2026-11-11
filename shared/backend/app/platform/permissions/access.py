"""One permission system (ADR-006 phase 3, #94).

- Permissions are declared by modules in their manifest ("permissions": [{"id", "name", ...}]).
- A role is a list of permissions: the platform's standard roles (no workspace), then the
  workspace's own roles. sys_roles.grants holds the list.
- A user is assigned roles (user_role_assignments) and acts as one at a time
  (users.active_role_id). Every check uses the acting role's permissions only: no "*", no
  role-name bypass. Switching role is recorded in the audit log.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


CLINICAL_ROLES = ("doctor", "nurse", "lab_tech", "pharmacist")


def declared_permissions() -> list[dict]:
    """Every permission modules declare: [{"id", "name", "name_en", "module"}]."""
    from app.framework.loader import manifest_index

    out, seen = [], set()
    for module_id, manifest in sorted(manifest_index().items()):
        for p in manifest.get("permissions", []):
            entry = p if isinstance(p, dict) else {"id": p}
            if entry["id"] not in seen:
                seen.add(entry["id"])
                out.append({**entry, "module": module_id})
    return out


def all_permissions() -> list[str]:
    return sorted(p["id"] for p in declared_permissions())


_standard_roles_synced = False


async def ensure_standard_roles(db: AsyncSession | None = None) -> None:
    """The platform's standard roles exist with their current permissions. Synced once per process
    in a session of its own with no workspace bound: these rows belong to the platform, and a
    request's session runs as the workspace role, which can't write them (#112)."""
    global _standard_roles_synced
    if _standard_roles_synced:
        return
    import json

    from app.db.base import AsyncSessionLocal
    from app.platform.permissions.roles import ROLE_LABELS, standard_permissions
    from app.platform.tenancy.context import current_tenant_id

    token = current_tenant_id.set(None)
    try:
        async with AsyncSessionLocal() as own:
            await own.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            for code, label in ROLE_LABELS.items():
                await own.execute(text("""
                    INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants)
                    VALUES (gen_random_uuid(), NULL, :code, :name, :code, true, :clinical, CAST(:grants AS jsonb))
                    ON CONFLICT (code) WHERE tenant_id IS NULL DO UPDATE SET grants = EXCLUDED.grants, name = EXCLUDED.name
                """), {"code": code, "name": label, "clinical": code in CLINICAL_ROLES,
                       "grants": json.dumps(standard_permissions(code))})
            await own.commit()
    finally:
        current_tenant_id.reset(token)
    _standard_roles_synced = True


async def role_by_code(db: AsyncSession, code: str) -> dict | None:
    await ensure_standard_roles()
    row = (await db.execute(text("SELECT * FROM sys_roles WHERE code = :c AND tenant_id IS NULL"), {"c": code})).mappings().first()
    return dict(row) if row else None


async def roles_of(db: AsyncSession, user_id) -> list[dict]:
    """The roles a user is assigned (active, in their validity window)."""
    rows = (await db.execute(text("""
        SELECT r.id, r.code, r.name, r.name_en, r.tenant_id, r.grants
        FROM user_role_assignments a JOIN sys_roles r ON r.id = a.role_id
        WHERE a.user_id = :u AND a.is_active
          AND (a.valid_from IS NULL OR a.valid_from <= now()) AND (a.valid_until IS NULL OR a.valid_until > now())
        ORDER BY a.created_at
    """), {"u": user_id})).mappings().all()
    return [dict(r) for r in rows]


async def load_acting(db: AsyncSession, user) -> None:
    """Set user.acting_role, user.assigned_roles and user.effective_permissions for this request."""
    # Standard roles hold every permission modules declare (admin) or their defaults; sync them
    # before the first check in this process, so a newly declared permission (e.g. `designer`)
    # reaches them at once rather than after something else happens to sync. Once per process.
    await ensure_standard_roles()
    roles = await roles_of(db, user.id)
    acting = next((r for r in roles if r["id"] == getattr(user, "active_role_id", None)), roles[0] if roles else None)
    user.assigned_roles = roles
    user.acting_role = acting
    user.effective_permissions = frozenset(acting["grants"] or []) if acting else frozenset()


def can(user, *perms: str) -> bool:
    granted = getattr(user, "effective_permissions", frozenset())
    return any(p in granted for p in perms)


async def assign_roles(db: AsyncSession, user, role_ids: list[uuid.UUID], active_role_id: uuid.UUID | None = None) -> None:
    """Replace a user's role assignments; the acting role is kept if still assigned."""
    if not role_ids:
        raise HTTPException(400, "يجب تعيين دور واحد على الأقل")
    found = (await db.execute(text("SELECT id FROM sys_roles WHERE id = ANY(:ids)"), {"ids": list(role_ids)})).scalars().all()
    if set(found) != set(role_ids):
        raise HTTPException(404, "دور غير موجود")
    await db.execute(text("DELETE FROM user_role_assignments WHERE user_id = :u"), {"u": user.id})
    for rid in role_ids:
        await db.execute(text(
            "INSERT INTO user_role_assignments (id, user_id, role_id, is_active, tenant_id) VALUES (gen_random_uuid(), :u, :r, true, :t)"
        ), {"u": user.id, "r": rid, "t": user.tenant_id})
    keep = active_role_id or getattr(user, "active_role_id", None)
    await db.execute(text("UPDATE users SET active_role_id = :r WHERE id = :u"),
                     {"r": keep if keep in role_ids else role_ids[0], "u": user.id})


async def set_access(db: AsyncSession, user, role_code: str, permissions: list[str] | None = None) -> None:
    """Give a user one role: the standard role for role_code, or, when their permissions differ
    from it, a workspace role of their own (so their access is exactly `permissions`)."""
    standard = await role_by_code(db, role_code)
    if permissions is None or (standard and sorted(set(permissions)) == sorted(standard["grants"] or [])):
        if not standard:
            raise HTTPException(400, f"Invalid role: {role_code}")
        await assign_roles(db, user, [standard["id"]])
        return
    import json

    unknown = set(permissions) - set(all_permissions())
    if unknown:
        raise HTTPException(400, f"صلاحيات غير معروفة: {', '.join(sorted(unknown))}")
    code = f"{role_code}-{str(user.id)[:8]}"
    label = (standard["name"] if standard else role_code) + f" — {user.full_name or user.username}"
    rid = (await db.execute(text("""
        INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants)
        VALUES (gen_random_uuid(), :t, :code, :name, :code, false, :clinical, CAST(:g AS jsonb))
        ON CONFLICT (code, tenant_id) DO UPDATE SET grants = EXCLUDED.grants, name = EXCLUDED.name
        RETURNING id
    """), {"t": user.tenant_id, "code": code, "name": label, "clinical": role_code in CLINICAL_ROLES,
           "g": json.dumps(sorted(set(permissions)))})).scalar_one()
    await assign_roles(db, user, [rid])


async def switch_role(db: AsyncSession, user, role_id: uuid.UUID) -> dict:
    """Act as another of one's assigned roles (recorded in the audit log)."""
    from app.platform.audit.service import log as audit_log

    roles = await roles_of(db, user.id)
    target = next((r for r in roles if r["id"] == role_id), None)
    if not target:
        raise HTTPException(403, "هذا الدور غير مُسند إليك")
    previous = getattr(user, "acting_role", None)
    await db.execute(text("UPDATE users SET active_role_id = :r WHERE id = :u"), {"r": role_id, "u": user.id})
    await audit_log(db, "user", "switch_role", user.id, user.full_name, user.id,
                    {"from": previous["code"] if previous else None, "to": target["code"],
                     "at": datetime.now(UTC).isoformat()}, f"العمل بدور {target['name']}")
    user.active_role_id = role_id
    await load_acting(db, user)
    return target


def ensure_within(user, permissions) -> None:
    """No privilege escalation: you can only grant what your acting role holds."""
    beyond = set(permissions) - set(getattr(user, "effective_permissions", frozenset()))
    if beyond:
        raise HTTPException(403, f"لا يمكنك منح صلاحيات لا يملكها دورك الحالي: {', '.join(sorted(beyond))}")


async def available_roles(db: AsyncSession) -> list[dict]:
    """The platform's standard roles, then this workspace's own. (Catalogue roles seeded by
    /authz/seed that hold no permissions are left out.)"""
    from app.platform.permissions.roles import ROLE_LABELS

    await ensure_standard_roles()
    rows = (await db.execute(text(
        "SELECT id, code, name, name_en, grants, tenant_id IS NULL AS standard FROM sys_roles"
        " WHERE tenant_id IS NOT NULL OR code = ANY(:std) ORDER BY tenant_id NULLS FIRST, name"
    ), {"std": list(ROLE_LABELS)})).mappings().all()
    return [dict(r) for r in rows]

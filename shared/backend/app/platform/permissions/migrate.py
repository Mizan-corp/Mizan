"""Migration v54: every user gets roles with exactly the access they had (ADR-006 phase 3).

Before: a user's access was their own permission list, plus what their role name granted (admin,
owner and platform staff passed every check; the clinic and shift checks looked at role names).
Now: the standard role for their role name if that is exactly their access, otherwise a workspace
role of their own with exactly that access. Idempotent: users who already have roles are skipped.
"""
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.permissions.access import all_permissions, ensure_standard_roles, set_access
from app.platform.permissions.roles import FULL_ACCESS_ROLES, ROLE_IMPLIED_PERMISSIONS, ROLE_LABELS


def access_before(role: str, permissions: list | None, is_superadmin: bool) -> list[str]:
    granted = set(permissions or [])
    if role in FULL_ACCESS_ROLES or is_superadmin or "*" in granted:
        return all_permissions()
    known = set(all_permissions())
    return sorted((granted | set(ROLE_IMPLIED_PERMISSIONS.get(role, []))) & known)


async def migrate_users(db: AsyncSession) -> None:
    await ensure_standard_roles()
    users = (await db.execute(text("""
        SELECT u.id, u.tenant_id, u.username, u.full_name, u.role, u.permissions, u.is_superadmin
        FROM users u
        WHERE NOT EXISTS (SELECT 1 FROM user_role_assignments a WHERE a.user_id = u.id)
    """))).mappings().all()
    for u in users:
        role = u["role"] if u["role"] in ROLE_LABELS else "admin"
        user = SimpleNamespace(id=u["id"], tenant_id=u["tenant_id"], username=u["username"],
                               full_name=u["full_name"], active_role_id=None)
        await set_access(db, user, role, access_before(u["role"], u["permissions"], bool(u["is_superadmin"])))

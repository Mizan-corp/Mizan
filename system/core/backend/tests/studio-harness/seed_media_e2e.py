"""Seed the studio E2E database: full schema (create_all, as local DBs get), one
tenant, one real active user holding the standard admin role, and print a Bearer
token for the bridge. Real auth path: the API validates this token via the normal
get_current_user/_session_user flow (no identity override anywhere in this run)."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.environ.get("STUDIO_BACKEND_ROOT", "/tmp/mizan-push/system/core/backend"))
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres@127.0.0.1:5544/mizan_studio_e2e"
os.environ.setdefault("SECRET_KEY", "studio-e2e-secret")


TENANT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
USER_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")


async def main():
    from app.models.registry import load_all_models
    load_all_models()
    from app.db.base import Base, engine
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    from app.platform.tenancy.models import Tenant
    from app.platform.auth.models.user import User
    from app.platform.permissions.access import ensure_standard_roles
    import bcrypt

    pwd = type("H", (), {"hash": staticmethod(
        lambda p: bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode())})()
    async with Session() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(Tenant(id=TENANT_ID, name="Studio E2E", active_modules=["core", "inventory", "helpdesk"]))
        await db.commit()
        db.add(User(id=USER_ID, tenant_id=TENANT_ID, username="studio-e2e", full_name="Studio E2E",
                    role="admin", account_type="owner", is_active=True, is_manager=True,
                    password_hash=pwd.hash("e2e-not-used-anywhere")))
        await db.commit()
        await ensure_standard_roles()
        admin = (await db.execute(text(
            "SELECT id FROM sys_roles WHERE code='admin' AND tenant_id IS NULL"))).scalar_one()
        await db.execute(text(
            "INSERT INTO user_role_assignments (id, user_id, role_id, is_active, tenant_id)"
            " VALUES (gen_random_uuid(), :u, :r, true, :t)"),
            {"u": USER_ID, "r": admin, "t": TENANT_ID})
        await db.execute(text("UPDATE users SET active_role_id=:r WHERE id=:u"),
                         {"u": USER_ID, "r": admin})
        await db.commit()

    from app.platform.auth.security import create_access_token
    token = create_access_token({"sub": str(USER_ID), "tid": str(TENANT_ID)})
    print(f"TOKEN={token}")
    await engine.dispose()


asyncio.run(main())

"""First install: build the database and create the licensed workspace.

    python -m app.onprem.setup --licence KEY --admin-password PASS [--admin-username NAME]
                               [--admin-name "Full name"] [--demo]

The installer runs this once (and it's safe to run again: it only fills in what's
missing). The schema is built the same way as a fresh cloud database: the baseline
schema, the models' tables, the foundation SQL, then every migration. The
workspace is created with the id, name and modules the licence carries, so the
install and its cloud registration refer to the same workspace.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy import func, select, text

from app.platform.licensing import keys as licensing
from app.catalog import canonical_activity, canonical_modules
from app.framework.activation import SECTOR_TO_PRESET, set_active_modules
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import bind_tenant, install_tenancy_events
from app.db.base import AsyncSessionLocal, Base, engine
from app.db.migrations import FOUNDATION_SQL, apply_migrations, split_statements
from app.models.registry import load_all_models
from app.onprem import state

logger = logging.getLogger("mizan.onprem.setup")
BASELINE = Path(__file__).resolve().parent.parent / "db" / "baseline_schema.sql"


async def build_schema(workspace_id: uuid.UUID, workspace_name: str) -> list[str]:
    """Create or bring up to date the schema. Returns the migrations applied now."""
    load_all_models()
    async with engine.begin() as conn:
        fresh = await conn.scalar(text("SELECT to_regclass('public.tenants') IS NULL"))
        if fresh:
            # pg_dump's \restrict lines are psql commands, not SQL.
            script = "\n".join(ln for ln in BASELINE.read_text(encoding="utf-8").splitlines() if not ln.startswith("\\"))
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(script)
            # pg_dump empties search_path for its session; put it back for what follows.
            await conn.execute(text("SET search_path TO public"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TYPE doc_type_enum ADD VALUE IF NOT EXISTS 'safe_deposit'"))
        # Our workspace first, so the foundation step doesn't add a default one.
        await conn.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        await conn.execute(
            text("INSERT INTO tenants (id, name) SELECT :id, :name WHERE NOT EXISTS (SELECT 1 FROM tenants)"),
            {"id": workspace_id, "name": workspace_name},
        )

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', false)"))
        for stmt in split_statements(FOUNDATION_SQL):
            try:
                async with db.begin_nested():
                    await db.execute(text(stmt))
            except Exception as e:  # idempotent DDL: "already exists" and friends
                logger.debug("foundation: %s", e)
        await db.commit()
        return await apply_migrations(db)


async def create_workspace(payload: dict, *, admin_username: str, admin_password: str, admin_name: str, demo: bool) -> dict:
    from app.models.settings import StoreSetting
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.services.demo_seed import seed_demo

    ws = payload["workspace"]
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        tenant = await db.get(Tenant, uuid.UUID(ws["id"]))
        if tenant is None:
            raise SystemExit("The database already holds another workspace. Use an empty database.")
        tenant.name = ws["name"]
        tenant.slug = ws.get("slug") or tenant.slug
        tenant.sector = tenant.business_type = canonical_activity(ws.get("sector") or "") or tenant.sector
        tenant.scale = ws.get("scale") or tenant.scale
        tenant.palette = ws.get("palette") or tenant.palette
        tenant.active_modules = canonical_modules(ws.get("modules") or []) or tenant.active_modules
        tenant.plan = payload.get("plan") or tenant.plan
        tenant.limits = payload.get("limits") or tenant.limits
        tenant.deployment_mode = payload["mode"]
        tenant.status = "active"
        tenant.trial_ends_at = None  # the licence decides, not a trial date
        await db.flush()

        await bind_tenant(db, tenant.id)
        created = False
        admin = await db.scalar(select(User).where(User.tenant_id == tenant.id, User.role == "admin").limit(1))
        if admin is None:
            admin = User(id=uuid.uuid4(), tenant_id=tenant.id, username=admin_username, full_name=admin_name,
                         role="admin", is_manager=True, permissions=["*"], password_hash=hash_password(admin_password))
            db.add(admin)
            await db.flush()
            created = True
            if demo:
                await seed_demo(db, tenant.id, admin.id, tenant.sector, tenant.scale, tenant.active_modules)
        await set_active_modules(db, tenant.active_modules, preset_id=SECTOR_TO_PRESET.get(tenant.sector))
        existing = set((await db.scalars(select(StoreSetting.key).where(StoreSetting.tenant_id == tenant.id))).all())
        for key, value in (("store_name", tenant.name), ("currency", "EGP")):
            if key not in existing:
                db.add(StoreSetting(tenant_id=tenant.id, key=key, value=json.dumps(value, ensure_ascii=False)))
        users = await db.scalar(select(func.count()).select_from(User).where(User.tenant_id == tenant.id))
        await db.commit()
        return {"workspace_id": str(tenant.id), "slug": tenant.slug, "admin": admin.username,
                "admin_created": created, "users": users}


async def run(key: str, *, admin_username: str | None, admin_password: str, admin_name: str | None, demo: bool) -> dict:
    payload = licensing.verify(key)
    install_tenancy_events()  # stamps tenant_id on new rows, as in the running app
    state.save_licence_key(key)
    install_id = state.installation_id()
    owner = payload.get("owner") or {}
    applied = await build_schema(uuid.UUID(payload["workspace"]["id"]), payload["workspace"]["name"])
    result = await create_workspace(
        payload,
        admin_username=admin_username or owner.get("login") or "admin",
        admin_password=admin_password,
        admin_name=admin_name or owner.get("full_name") or "مدير النظام",
        demo=demo,
    )
    await engine.dispose()
    return {**result, "installation_id": str(install_id), "mode": payload["mode"],
            "valid_until": payload["valid_until"], "migrations_applied": len(applied)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.onprem.setup", description=__doc__.splitlines()[0])
    p.add_argument("--licence", required=True, help="the licence key from the owner panel")
    p.add_argument("--admin-password", required=True)
    p.add_argument("--admin-username", help="defaults to the owner's username")
    p.add_argument("--admin-name", help="defaults to the owner's name")
    p.add_argument("--demo", action="store_true", help="fill with sample data for the workspace's business type")
    args = p.parse_args(argv)
    if len(args.admin_password) < 8:
        p.error("the admin password must be at least 8 characters")
    try:
        result = asyncio.run(run(args.licence, admin_username=args.admin_username, admin_password=args.admin_password,
                                 admin_name=args.admin_name, demo=args.demo))
    except licensing.LicenceError as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

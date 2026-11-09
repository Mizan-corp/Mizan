"""First-run bootstrap: create the first admin on an empty database.

Runs after migrations (`python manage.py db migrate` calls it inside the
system-api container). It does nothing unless the database has no users at all, so it is
safe to run against any environment, including production.

    python -m app.db.bootstrap

Creates two accounts in the default workspace:
- the workspace admin, from MIZAN_ADMIN_USERNAME / MIZAN_ADMIN_PASSWORD
  (default ammar / changeme), who signs in to the app, plus the matching
  owner account for the owner panel (same name and password);
- the platform admin, from MIZAN_PLATFORM_USERNAME / MIZAN_PLATFORM_PASSWORD
  (default platform / changeme), who signs in to the admin panel.
Change both passwords after the first sign-in.
"""
import asyncio
import json
import os
import uuid

from sqlalchemy import func, select, text

from app.core.security import hash_password
from app.core.tenancy import bind_tenant
from app.db.base import AsyncSessionLocal
from app.models.registry import load_all_models
from app.models.owner import OwnerAccount
from app.models.settings import StoreSetting
from app.models.tenant import Tenant
from app.models.user import User

DEFAULT_WORKSPACE_NAME = "ميزان"


async def bootstrap() -> str:
    load_all_models()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        if await db.scalar(select(func.count()).select_from(User)):
            return "users already exist, nothing to do"

        tenant = await db.scalar(select(Tenant).order_by(Tenant.created_at).limit(1))
        if tenant is None:
            tenant = Tenant(id=uuid.uuid4(), name=DEFAULT_WORKSPACE_NAME)
            db.add(tenant)
            await db.flush()

        await bind_tenant(db, tenant.id)
        username = os.environ.get("MIZAN_ADMIN_USERNAME", "ammar")
        password_hash = hash_password(os.environ.get("MIZAN_ADMIN_PASSWORD", "changeme"))
        owner = OwnerAccount(id=uuid.uuid4(), login=username.lower(), full_name="مدير النظام", password_hash=password_hash)
        db.add(owner)
        await db.flush()
        tenant.owner_account_id = owner.id
        db.add(User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            username=username,
            full_name="مدير النظام",
            role="admin",
            permissions=["*"],
            is_manager=True,
            password_hash=password_hash,
            owner_account_id=owner.id,
        ))
        db.add(User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            username=os.environ.get("MIZAN_PLATFORM_USERNAME", "platform"),
            full_name="Platform admin",
            role="admin",
            permissions=["*"],
            is_superadmin=True,
            password_hash=hash_password(os.environ.get("MIZAN_PLATFORM_PASSWORD", "changeme")),
        ))
        existing = set((await db.scalars(select(StoreSetting.key).where(StoreSetting.tenant_id == tenant.id))).all())
        for key, value in (("store_name", tenant.name), ("currency", "EGP")):
            if key not in existing:
                db.add(StoreSetting(tenant_id=tenant.id, key=key, value=json.dumps(value, ensure_ascii=False)))
        await db.commit()
        platform = os.environ.get("MIZAN_PLATFORM_USERNAME", "platform")
        return f"created app admin '{username}' and admin-panel account '{platform}' in workspace '{tenant.name}'"


if __name__ == "__main__":
    print(asyncio.run(bootstrap()))

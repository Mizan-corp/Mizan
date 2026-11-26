"""Local E2E app for the site media library: real router, real require_perm gate,
real disk storage, real StaticFiles serving. Only substituted seam: get_current_user
(identity), exactly like the committed live-PG harness. Tenant T1 has site.manage;
switch X-E2E-Tenant to the second id to act as the other workspace (no rows visible).
"""
import os
import sys
import uuid
from types import SimpleNamespace

sys.path.insert(0, "/tmp/mizan-push/system/core/backend")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.db.base import engine  # noqa: E402
from app.models.registry import load_all_models  # noqa: E402

load_all_models()

from app.platform.site.media import media_router  # noqa: E402
from app.dependencies import get_current_user  # noqa: E402
from app.platform.tenancy.context import current_tenant_id, install_tenancy_events  # noqa: E402

install_tenancy_events()  # the factory's tenant_id injection on flush, as in production

T1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
T2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/media-e2e-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()


@app.middleware("http")
async def bind_tenant(request: Request, call_next):
    tid = T2 if request.headers.get("x-e2e-tenant") == str(T2) else T1
    token = current_tenant_id.set(tid)
    try:
        return await call_next(request)
    finally:
        current_tenant_id.reset(token)


async def fake_user(request: Request):
    tid = current_tenant_id.get()
    perms = set() if request.headers.get("x-e2e-noperm") == "1" else {"site.manage"}
    return SimpleNamespace(tenant_id=tid, effective_permissions=frozenset(perms), id=uuid.uuid4())


app.dependency_overrides[get_current_user] = fake_user
app.include_router(media_router, prefix="/api")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
async def create_tables():
    from app.db.base import Base
    tables = [Base.metadata.tables[t] for t in
              ("owner_accounts", "tenants", "workspace_files", "site_pages", "site_page_revisions",
              "site_settings")]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables, checkfirst=True))
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.platform.tenancy.models import Tenant
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        from sqlalchemy import select
        if not (await db.execute(select(Tenant).where(Tenant.id == T1))).scalar_one_or_none():
            db.add_all([Tenant(id=T1, name="E2E One", active_modules=["core"]),
                        Tenant(id=T2, name="E2E Two", active_modules=["core"])])
            await db.commit()

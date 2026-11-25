"""Integration check for the Help Desk source-adapter registry (f9348e5).

Runs under Python 3.12 against a real local PostgreSQL 16 instance (the app's
supported runtime + production DB engine), using the app's OWN engine/get_db
(no DB seams substituted). The only substituted seam is get_current_user
(identity), so the REAL require_perm / require_module / can() gates and the
REAL list_source_work -> SOURCES registry path execute end to end.

Covers:
 1. successful existing-source response (field_service + real_estate rows
    projected through the registry, feature flags from real settings storage)
 2. tenant scoping (other tenant's rows never appear)
 3. unavailable-source diagnostic (bogus adapter -> unavailable_sources entry,
    no crash, existing rows still returned)
 4. permission/tenant gates unchanged at the HTTP boundary:
    no permission -> 403; module inactive -> 403; permitted -> 200
"""
import asyncio
import json
import os
import sys
import uuid
from types import SimpleNamespace

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = os.environ.get("MIZAN_LIVE_PG_URL", "postgresql+asyncpg://postgres@127.0.0.1:5544/mizan_it")
os.environ.setdefault("SECRET_KEY", "integration-check-not-used-for-signing")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.base import Base, engine  # noqa: E402  (app's own engine)
from app.platform.auth.models.owner import OwnerAccount  # noqa: E402,F401
from app.platform.tenancy.models import Tenant  # noqa: E402
from app.platform.settings.models import StoreSetting  # noqa: E402
from app.platform.tenancy.context import current_tenant_id  # noqa: E402
from app.activities.maintenance.modules.field_service.models import FsmWorkOrder  # noqa: E402
from app.activities.property.modules.real_estate import models as rec  # noqa: E402
from app.activities.general.modules.helpdesk import work as helpdesk_work  # noqa: E402
from app.activities.general.modules.helpdesk.sources import SOURCES, SourceAdapter  # noqa: E402
from app.activities.general.modules.helpdesk.router import router as helpdesk_router  # noqa: E402
from app.dependencies import get_current_user  # noqa: E402
from app.models.registry import load_all_models  # noqa: E402

load_all_models()  # register every mapper, as the app factory does at startup

T1 = uuid.uuid4()
T2 = uuid.uuid4()
TABLES = [
    "owner_accounts", "tenants", "store_settings",
    "rec_properties", "rec_units", "rec_maintenance_tickets", "fsm_work_orders",
]

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (" :: " + detail if detail else ""))


async def main():
    tables = [Base.metadata.tables[t] for t in TABLES]
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables, checkfirst=True))
    except OSError as e:
        print(f"SKIP: no live PostgreSQL reachable ({e.__class__.__name__}); set MIZAN_LIVE_PG_URL")
        await engine.dispose()
        sys.exit(0)

    from sqlalchemy.ext.asyncio import async_sessionmaker
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # ---- seed real rows through the ORM ------------------------------------
    async with Session() as db:
        t1 = Tenant(id=T1, name="T One", active_modules=["helpdesk", "field_service", "real_estate"])
        t2 = Tenant(id=T2, name="T Two", active_modules=["helpdesk", "field_service", "real_estate"])
        db.add_all([t1, t2])
        await db.commit()
        db.add(StoreSetting(tenant_id=T1, key="mod_settings_helpdesk",
                            value=json.dumps({"service_catalog": True, "work_actuals": True})))
        prop1 = rec.RecProperty(id=str(uuid.uuid4()), tenant_id=T1, property_code="P-1",
                                property_name="P1", property_type="mixed_use", city="c", district="d")
        unit1 = rec.RecUnit(id=str(uuid.uuid4()), tenant_id=T1, property_id=prop1.id,
                            unit_number="U1", floor="G")
        db.add(prop1)
        await db.flush()
        db.add(unit1)
        await db.flush()
        db.add(FsmWorkOrder(id=str(uuid.uuid4()), tenant_id=T1, order_ref="WO-T1-1",
                            client_name="Acme", client_phone="1", site_address="s",
                            equipment_type="chiller", issue_description="leak in unit 1",
                            priority_sla="standard_24h", assigned_technician="tech",
                            van_code="V1", scheduled_date="2026-11-25", status="dispatched"))
        db.add(FsmWorkOrder(id=str(uuid.uuid4()), tenant_id=T2, order_ref="WO-T2-OTHER",
                            client_name="Other", client_phone="2", site_address="s",
                            equipment_type="pump", issue_description="other tenant row",
                            priority_sla="standard_24h", assigned_technician="tech",
                            van_code="V2", scheduled_date="2026-11-25", status="dispatched"))
        db.add(rec.RecMaintenanceTicket(id=str(uuid.uuid4()), tenant_id=T1, unit_id=unit1.id,
                                        ticket_ref="MT-T1-1", description="AC not cooling",
                                        reported_by="tenant", status="open"))
        db.add(rec.RecMaintenanceTicket(id=str(uuid.uuid4()), tenant_id=T2, unit_id=unit1.id,
                                        ticket_ref="MT-T2-OTHER", description="other tenant ticket",
                                        reported_by="tenant", status="open"))
        await db.commit()

    user_t1 = SimpleNamespace(tenant_id=T1)

    # ---- 1+2: direct endpoint-function call, real session/settings ----------
    tok = current_tenant_id.set(T1)
    async with Session() as db:
        payload = await helpdesk_work.list_source_work(db, user_t1)
    refs = {i.get("reference", "") for i in payload["items"]}
    srcs = {i.get("source_module") for i in payload["items"]}
    check("existing sources returned via registry",
          srcs == {"field_service", "real_estate"}, f"sources={sorted(srcs)}")
    check("tenant scoping holds (no other-tenant rows)",
          "WO-T1-1" in refs and "MT-T1-1" in refs and "WO-T2-OTHER" not in refs and "MT-T2-OTHER" not in refs,
          f"refs={sorted(refs)}")
    check("no unavailable sources when all resolve", payload["unavailable_sources"] == [])
    check("feature flags from real settings storage",
          payload["work_actuals_enabled"] is True and payload["work_intake_enabled"] is False,
          f"flags={payload['work_actuals_enabled']},{payload['work_intake_enabled']}")
    check("source_modules reflects active modules",
          payload["source_modules"] == ["field_service", "real_estate"], str(payload["source_modules"]))

    # ---- 3: unavailable-source diagnostic ----------------------------------
    bogus = SourceAdapter("hotel_engineering", "app.activities.hotel.modules.pms.models:NoSuchModel", ())
    helpdesk_work.SOURCES = (*SOURCES, bogus)
    # the diagnostic path fires only when the source module is ACTIVE but its
    # code is absent, so activate it on the tenant first
    async with Session() as db:
        t = await db.get(Tenant, T1)
        t.active_modules = ["helpdesk", "field_service", "real_estate", "hotel_engineering"]
        await db.commit()
    try:
        async with Session() as db:
            payload2 = await helpdesk_work.list_source_work(db, user_t1)
        check("absent source degrades to diagnostic, no crash",
              payload2["unavailable_sources"] == ["hotel_engineering"] and len(payload2["items"]) == len(payload["items"]),
              f"unavailable={payload2['unavailable_sources']}, items={len(payload2['items'])}")
    finally:
        helpdesk_work.SOURCES = SOURCES
        async with Session() as db:
            t = await db.get(Tenant, T1)
            t.active_modules = ["helpdesk", "field_service", "real_estate"]
            await db.commit()

    # ---- 4: HTTP boundary, real router + real gates -------------------------
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(helpdesk_router, prefix="/api")

    def identity(perms):
        async def _user():
            current_tenant_id.set(T1)
            return SimpleNamespace(tenant_id=T1, effective_permissions=frozenset(perms), id=uuid.uuid4())
        return _user

    async def hit(perms):
        app.dependency_overrides[get_current_user] = identity(perms)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.get("/api/helpdesk/work")

    r = await hit(set())
    check("no permission -> 403 (real require_perm)", r.status_code == 403, f"status={r.status_code}")

    r = await hit({"helpdesk:work:view", "operations"})
    body = r.json() if r.status_code == 200 else {}
    check("with permissions -> 200 through real router", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        refs = {i.get("reference", "") for i in body["items"]}
        check("HTTP payload matches direct-call payload (registry path)",
              refs == {"WO-T1-1", "MT-T1-1"}, f"refs={sorted(refs)}")

    # module gate: deactivate helpdesk for this tenant, expect 403 from require_module
    async with Session() as db:
        t = await db.get(Tenant, T1)
        t.active_modules = ["field_service", "real_estate"]
        await db.commit()
    r = await hit({"helpdesk:work:view", "operations"})
    check("helpdesk module inactive -> 403 (real require_module)", r.status_code == 403, f"status={r.status_code}")
    async with Session() as db:
        t = await db.get(Tenant, T1)
        t.active_modules = ["helpdesk", "field_service", "real_estate"]
        await db.commit()

    current_tenant_id.reset(tok)
    await engine.dispose()

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


asyncio.run(main())

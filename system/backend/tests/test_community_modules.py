"""Community modules in a workspace (ADR-007 step 2): install, records, references, permissions."""
import os
import types
import uuid

import pytest
from fastapi import HTTPException

import main  # noqa: F401
from app.framework import package as mzm
from tests.test_community_packages import MANIFEST, developer, files

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")

NOTE = {"id": "note", "name": "ملاحظة", "name_en": "Note", "title": "text",
        "fields": [{"key": "text", "type": "text", "label": "الملاحظة", "required": True},
                   {"key": "visit", "type": "reference", "to": "visit", "label": "الزيارة"}]}


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


def signed_package():
    manifest = {**MANIFEST, "entities": ["visit", "note"],
                "menu": [*MANIFEST["menu"], {"entity": "note", "label": "الملاحظات"}]}
    key, cert = developer()
    body = {**files(manifest), "entities/note.json": __import__("json").dumps(NOTE).encode()}
    return mzm.verify(mzm.build(body, key, cert))


async def test_install_records_and_permissions():
    from sqlalchemy import text

    from app.db.base import AsyncSessionLocal
    from app.platform.community import service
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    tid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"Community {tid.hex[:6]}", slug=f"comm-{tid.hex[:8]}", status="active"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tid)
            pkg = signed_package()
            with pytest.raises(HTTPException) as e:
                await service.install(db, pkg, None, approved_scopes=["customers:read"])  # not everything approved
            assert e.value.status_code == 409
            await service.install(db, pkg, None, approved_scopes=pkg.manifest["scopes"])

            from app.modules.general.contacts.models.party import Customer

            customer = uuid.uuid4()
            db.add(Customer(id=customer, name="عميل الزيارات"))
            await db.commit()

            # Permissions: the visit screen needs acme.visits.view; notes are open to everyone.
            clerk = types.SimpleNamespace(effective_permissions=frozenset())
            manager = types.SimpleNamespace(effective_permissions=frozenset({"acme.visits.view"}))
            assert [i["id"] for i in await service.menu_items(db, clerk)] == ["acme.visits.note"]
            assert {i["path"] for i in await service.menu_items(db, manager)} == {"/x/acme.visits/visit", "/x/acme.visits/note"}
            with pytest.raises(HTTPException) as e:
                await service.module_entity(db, clerk, "acme.visits", "visit")
            assert e.value.status_code == 403
            assert [p["id"] for p in await service.workspace_permissions(db)] == ["acme.visits.view"]

            m, visit = await service.module_entity(db, manager, "acme.visits", "visit")
            with pytest.raises(HTTPException) as e:
                await service.create_record(db, m, visit, {"on": "2026-11-12"}, None)  # customer is required
            assert "حقول مطلوبة" in e.value.detail
            with pytest.raises(HTTPException):
                await service.create_record(db, m, visit, {"customer": str(uuid.uuid4())}, None)  # no such customer
            with pytest.raises(HTTPException):
                await service.create_record(db, m, visit, {"customer": str(customer), "state": "ملغاة"}, None)
            r = await service.create_record(db, m, visit, {"customer": str(customer), "on": "2026-11-12T09:00",
                                                           "fee": "150.5", "state": "مجدولة"}, None)
            assert r.data == {"customer": str(customer), "on": "2026-11-12", "fee": "150.50", "state": "مجدولة"}

            _, note = await service.module_entity(db, clerk, "acme.visits", "note")
            n = await service.create_record(db, m, note, {"text": "اتصل قبلها", "visit": str(r.id)}, None)
            listed = await service.list_records(db, m, visit, None, 1)
            assert listed["total"] == 1 and listed["labels"][str(customer)] == "عميل الزيارات"
            notes = await service.list_records(db, m, note, "اتصل", 1)
            assert notes["total"] == 1 and notes["labels"][str(r.id)] == "عميل الزيارات"  # a visit is titled by its customer

            await service.update_record(db, m, visit, r, {"state": "تمت"})
            assert (await service.get_record(db, m, visit, r.id)).data["state"] == "تمت"
            with pytest.raises(HTTPException):
                await service.update_record(db, m, visit, r, {"customer": None})  # would leave a required field empty

            # Uninstalled: hidden, records kept; reinstalled: back.
            await service.uninstall(db, "acme.visits")
            assert await service.menu_items(db, manager) == []
            await service.install(db, pkg, None, approved_scopes=pkg.manifest["scopes"])
            assert (await service.list_records(db, m, visit, None, 1))["total"] == 1
            await service.delete_record(db, n)
            assert (await service.list_records(db, m, note, None, 1))["total"] == 0
            await service.uninstall(db, "acme.visits", delete_records=True)
            assert await db.scalar(text("SELECT count(*) FROM ext_records WHERE tenant_id = :t"), {"t": tid}) == 0
    finally:
        current_tenant_id.set(None)
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await db.commit()


async def test_installing_from_a_file_over_http():
    """Inspect → approve scopes → install → menu → uninstall, as the module centre does it;
    a cashier can't install."""
    import json as _json

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from app.db.base import AsyncSessionLocal
    from app.platform.auth.models.user import User
    from app.platform.auth.security import create_access_token, hash_password
    from app.platform.permissions.access import set_access
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    tid = uuid.uuid4()
    tokens = {}
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"Install {tid.hex[:6]}", slug=f"inst-{tid.hex[:8]}", status="active"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tid)
            for role in ("admin", "cashier"):
                u = User(id=uuid.uuid4(), tenant_id=tid, username=f"{role}-{tid.hex[:6]}", full_name=role, role=role,
                         password_hash=hash_password("x"))
                db.add(u)
                await db.flush()
                await set_access(db, u, role)
                tokens[role] = create_access_token({"sub": str(u.id), "tid": str(tid)})
            await db.commit()
        current_tenant_id.set(None)

        key, cert = developer()
        data = mzm.build(files(), key, cert)
        upload = {"file": ("acme.visits-1.0.0.mzm", data, "application/zip")}
        admin = {"Authorization": f"Bearer {tokens['admin']}"}
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            assert (await c.post("/community/packages/inspect", files=upload,
                                 headers={"Authorization": f"Bearer {tokens['cashier']}"})).status_code == 403
            bad = await c.post("/community/packages/inspect", files={"file": ("x.mzm", b"nope", "application/zip")}, headers=admin)
            assert bad.status_code == 422 and "تعذر قبول الحزمة" in bad.json()["detail"]
            info = (await c.post("/community/packages/inspect", files=upload, headers=admin)).json()
            assert info["id"] == "acme.visits" and info["developer"] == "acme" and info["sends_to"] == "acme.example"
            assert [s["text"] for s in info["scopes"]] == ["قراءة العملاء", "عند تأكيد فاتورة بيع"]

            r = await c.post("/community/packages/install", files=upload, data={"approved_scopes": "[]"}, headers=admin)
            assert r.status_code == 409
            r = await c.post("/community/packages/install", files=upload, headers=admin,
                             data={"approved_scopes": _json.dumps([s["id"] for s in info["scopes"]])})
            assert r.status_code == 200, r.text
            assert [m["id"] for m in (await c.get("/community/modules", headers=admin)).json()["items"]] == ["acme.visits"]
            screens = (await c.get("/settings/screens", headers=admin)).json()
            assert any(g["id"] == "community" for g in screens["menu"])

            assert (await c.delete("/community/modules/acme.visits", headers=admin)).status_code == 204
            assert (await c.get("/community/modules", headers=admin)).json()["items"] == []
    finally:
        current_tenant_id.set(None)
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await db.commit()


async def test_the_extension_api_is_scoped_and_isolated():
    """ADR-007 D4: a module's server sees only its workspace, its records and its scopes."""
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from app.db.base import AsyncSessionLocal
    from app.modules.general.contacts.models.party import Customer
    from app.platform.community import service
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    key, cert = developer()
    pkg = mzm.verify(mzm.build(files(), key, cert))
    tenants, tokens = [uuid.uuid4(), uuid.uuid4()], {}
    async with AsyncSessionLocal() as db:
        for t in tenants:
            db.add(Tenant(id=t, name=f"Ext {t.hex[:6]}", slug=f"ext-{t.hex[:8]}", status="active"))
        await db.commit()
    try:
        for t in tenants:
            async with AsyncSessionLocal() as db:
                await bind_tenant(db, t)
                db.add(Customer(name=f"عميل {t.hex[:4]}"))
                await db.commit()
                await service.install(db, pkg, None, approved_scopes=pkg.manifest["scopes"])
                tokens[t] = (await service.issue_token(db, "acme.visits"))["token"]
            current_tenant_id.set(None)

        a, b = ({"Authorization": f"Bearer {tokens[t]}"} for t in tenants)
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            assert (await c.get("/ext/v1/me")).status_code == 401
            assert (await c.get("/ext/v1/me", headers={"Authorization": "Bearer mzx_nope"})).status_code == 401
            me = (await c.get("/ext/v1/me", headers=a)).json()
            assert me["workspace"]["id"] == str(tenants[0]) and me["scopes"] == ["customers:read", "events:sale.confirmed"]

            custs = (await c.get("/ext/v1/customers", headers=a)).json()
            assert [x["name"] for x in custs["items"]] == [f"عميل {tenants[0].hex[:4]}"]  # only its workspace
            assert (await c.get("/ext/v1/products", headers=a)).status_code == 403  # not granted
            assert (await c.post("/ext/v1/customers", headers=a, json={"name": "x"})).status_code == 403

            made = await c.post("/ext/v1/records/visit", headers=a, json={"customer": custs["items"][0]["id"], "state": "مجدولة"})
            assert made.status_code == 201, made.text
            rid = made.json()["id"]
            assert (await c.get(f"/ext/v1/records/visit/{rid}", headers=a)).status_code == 200
            assert (await c.get(f"/ext/v1/records/visit/{rid}", headers=b)).status_code == 404  # other workspace
            assert (await c.get("/ext/v1/records/visit", headers=b)).json()["total"] == 0
            # A customer from the other workspace can't be referenced.
            other = (await c.get("/ext/v1/customers", headers=b)).json()["items"][0]["id"]
            assert (await c.post("/ext/v1/records/visit", headers=a, json={"customer": other})).status_code == 422
            assert (await c.patch(f"/ext/v1/records/visit/{rid}", headers=a, json={"state": "تمت"})).json()["data"]["state"] == "تمت"
            assert (await c.get("/ext/v1/records/nope", headers=a)).status_code == 404

        # Rotating or uninstalling ends the old token.
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tenants[0])
            await service.uninstall(db, "acme.visits")
        current_tenant_id.set(None)
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            assert (await c.get("/ext/v1/me", headers=a)).status_code == 401
            assert (await c.get("/ext/v1/me", headers=b)).status_code == 200
    finally:
        current_tenant_id.set(None)
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE id = ANY(:t)"), {"t": tenants})
            await db.commit()

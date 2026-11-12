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

"""Retail (ADR-006 phase 8): the POS retail variant reads weighing-scale labels."""
import os
import uuid
from decimal import Decimal

import pytest

import main  # noqa: F401  (loads every model)
from app.core.exceptions import NotFoundError
from app.framework import variants
from app.modules.general.pos.variants.retail import hooks as retail


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


def label(item: str, value: int, prefix: str = "21") -> str:
    """A scale label: prefix, 5-digit item, 5-digit value, EAN-13 check digit."""
    body = f"{prefix}{item}{value:05d}"
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


def test_scale_labels_are_decoded():
    code = label("00123", 735)
    assert retail.ean13_ok(code)
    assert retail.decode(code, {}) == ("00123", 735)
    assert retail.decode(code[:-1] + str((int(code[-1]) + 1) % 10), {}) is None  # bad check digit
    assert retail.decode(label("00123", 735, prefix="62"), {}) is None  # a normal product barcode
    assert retail.decode(code, {"item_digits": 4}) == ("0012", 300735)
    assert retail.decode("12345", {}) is None


def test_retail_runs_its_pos_variant():
    assert variants.variant_of("pos", "retail") == "retail"
    assert variants.setting("pos", "scale_barcode", "retail")["item_digits"] == 5
    assert "scale_code" in {f["key"] for f in variants.variant("pos", "retail")["fields"]["product"]}


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")
async def test_the_till_adds_weighed_items(monkeypatch):
    from sqlalchemy import text

    from app.db.base import AsyncSessionLocal
    from app.modules.general.inventory.models.product import Product
    from app.modules.general.pos import service
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    tid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"Retail {tid.hex[:6]}", slug=f"retail-{tid.hex[:8]}", status="active", sector="retail"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tid)
            rice = Product(name="أرز 1 كجم", barcode=f"622{tid.int % 10**10:010d}", retail_price=Decimal("38.50"))
            cheese = Product(name="جبنة رومي (بالكيلو)", unit="كجم", retail_price=Decimal("320"), extra={"scale_code": "123"})
            db.add_all([rice, cheese])
            await db.commit()

            found = await service.scan(db, rice.barcode)
            assert found["product"].id == rice.id and found["qty"] == 1 and found["scale"] is None

            found = await service.scan(db, label("00123", 735))  # 735 g
            assert found["product"].id == cheese.id and found["qty"] == Decimal("0.735")
            assert found["scale"] == {"item": "00123", "weight_kg": "0.735"}

            real = variants.setting
            monkeypatch.setattr(variants, "setting", lambda m, k, a, d=None: (
                {"value": "price"} if (m, k) == ("pos", "scale_barcode") else real(m, k, a, d)))
            found = await service.scan(db, label("00123", 8000))  # 80.00 EGP of cheese at 320/kg
            assert found["qty"] == Decimal("0.250") and found["scale"]["price"] == "80"
            monkeypatch.setattr(variants, "setting", real)

            with pytest.raises(NotFoundError):
                await service.scan(db, label("00999", 500))  # no product with that scale code
            with pytest.raises(NotFoundError):
                await service.scan(db, label("00123", 0))  # an empty scale
    finally:
        current_tenant_id.set(None)
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM products WHERE tenant_id = :t"), {"t": tid})
            await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await db.commit()


def test_retail_layouts_by_role():
    from app.framework import screens

    for role, home in (("cashier", "pos.pos"), ("storekeeper", "inventory.inventory"), ("accountant", "finance.finance"), ("manager", "pos.pos")):
        layout = screens.defaults("retail", role)
        assert layout["home"] == home, role
        ids = [i["screen"] for g in layout["menu"] for i in g["items"]] + [layout["home"]]
        assert all(screens.screen(s, "retail") for s in ids), [s for s in ids if not screens.screen(s, "retail")]
    cashier = screens.defaults("retail", "cashier")
    assert [w["id"] for w in cashier["dashboard"]] == ["pos.shift_status", "reporting.sales_today", "pos.recent_sales"]


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")
async def test_retail_demo_data_has_weighed_items():
    from sqlalchemy import text

    from app.db.base import AsyncSessionLocal
    from app.framework.demo import seed_workspace
    from app.platform.auth.models.user import User
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    tid, uid = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"Demo {tid.hex[:6]}", slug=f"demo-{tid.hex[:8]}", status="active", sector="retail"))
        await db.flush()
        db.add(User(id=uid, tenant_id=tid, username=f"demo-{tid.hex[:8]}", full_name="Owner", role="admin", password_hash="x"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tid)
            await seed_workspace(db, tid, uid, "retail", scale="small")
            await db.commit()
            rows = (await db.execute(text(
                "SELECT unit, barcode, extra->>'scale_code' FROM products WHERE name LIKE '%(بالكيلو)%'"))).all()
            assert rows and all(u == "كجم" and b is None and plu for u, b, plu in rows)
            assert len({plu for *_, plu in rows}) == len(rows)
            assert (await db.scalar(text("SELECT count(*) FROM products WHERE unit = 'متر'"))) == 0
    finally:
        current_tenant_id.set(None)
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await db.commit()

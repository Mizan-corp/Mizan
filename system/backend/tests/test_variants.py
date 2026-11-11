"""Variants, hooks and fields (ADR-006 phase 4)."""
import os
import types
import uuid

import pytest
from fastapi import HTTPException

import main  # noqa: F401  (loads every model)
from app.framework import fields as F
from app.framework import hooks, variants


@pytest.fixture
def pharmacy_live(monkeypatch):
    """The pharmacy variants as if built (status active), whatever their files say today."""
    real = variants.all_variants()
    live = {m: {k: ({**v, "status": "active"} if k == "pharmacy" else v) for k, v in vs.items()} for m, vs in real.items()}
    monkeypatch.setattr(variants, "all_variants", lambda: live)
    yield live


def test_planned_variants_fall_back_to_standard(monkeypatch):
    real = variants.all_variants()
    planned = {m: {k: {**v, "status": "planned"} for k, v in vs.items()} for m, vs in real.items()}
    monkeypatch.setattr(variants, "all_variants", lambda: planned)
    assert variants.variant_of("pos", "pharmacy") == "standard"


def test_the_activity_chooses_the_variant(pharmacy_live):
    assert variants.variant_of("pos", "pharmacy") == "pharmacy"
    assert variants.variant_of("inventory", "pharmacy") == "pharmacy"
    assert variants.variant_of("pos", "retail") in ("retail", "standard")
    assert variants.variant_of("finance", "pharmacy") == "standard"
    assert variants.variant_of("pos", None) == "standard"
    assert variants.terms_for("pharmacy")["item"] == "دواء"
    assert variants.setting_defaults("inventory", "pharmacy")["fefo"] is True


def test_legacy_activities_follow_the_one_they_map_to():
    assert variants.activity("plumbing")["id"] == variants.activity("retail")["id"]


def test_variant_fields_are_the_activitys(pharmacy_live):
    keys = [f["key"] for f in F.variant_fields("product", "pharmacy")]
    assert "scientific_name" in keys and "requires_prescription" in keys
    assert F.variant_fields("product", "restaurant") == []


async def test_hooks_run_only_the_workspaces_variant(pharmacy_live, monkeypatch):
    calls = []
    fake = types.ModuleType("fake_hooks")

    async def before_confirm(db, activity_id=None, **ctx):
        calls.append((activity_id, ctx["n"]))
        return "ran"

    fake.before_confirm = before_confirm
    monkeypatch.setattr(hooks, "_hooks_module", lambda m, v: fake if (m, v) == ("pos", "pharmacy") else None)
    assert await hooks.emit("pos.before_confirm", None, activity_id="pharmacy", n=1) == ["ran"]
    assert await hooks.emit("pos.before_confirm", None, activity_id="restaurant", n=2) == []
    assert await hooks.emit("pos.after_confirm", None, activity_id="pharmacy", n=3) == []
    assert calls == [("pharmacy", 1)]


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")
async def test_workspace_fields_override_and_extend(pharmacy_live):
    from app.db.base import AsyncSessionLocal
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    tid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"Fields {tid.hex[:6]}", slug=f"fields-{tid.hex[:8]}", status="active", sector="pharmacy"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tid)
            db.add(F.WorkspaceField(record="product", key="strength", definition={"type": "text", "label": "العيار", "required": True}))
            db.add(F.WorkspaceField(record="product", key="shelf", definition={"type": "text", "label": "الرف"}))
            db.add(F.WorkspaceField(record="product", key="dosage_form", definition={"type": "text"}, hidden=True))
            await db.commit()
            defs = {f["key"]: f for f in await F.fields_for(db, "product", "pharmacy")}
            assert defs["strength"]["label"] == "العيار" and defs["strength"]["required"]
            assert "shelf" in defs and "dosage_form" not in defs

            clean = await F.clean_extra(db, "product", {"strength": "500mg", "requires_prescription": "true", "shelf": "A3"}, "pharmacy")
            assert clean == {"strength": "500mg", "requires_prescription": True, "shelf": "A3"}
            with pytest.raises(HTTPException):
                await F.clean_extra(db, "product", {"shelf": "A3"}, "pharmacy")  # strength is required now
            with pytest.raises(HTTPException):
                await F.clean_extra(db, "product", {"strength": "1g", "colour": "red"}, "pharmacy")  # unknown field
            assert await F.clean_extra(db, "sale_line", {"batch_number": "B1"}, "pharmacy") == {}  # read-only
            assert await F.clean_extra(db, "sale_line", {"batch_number": "B1"}, "pharmacy", system=True) == {"batch_number": "B1"}
    finally:
        current_tenant_id.set(None)
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text

            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await db.commit()


def test_every_activity_names_existing_variants():
    """activity.json "variants" only names variants the module has."""
    for f in variants.ACTIVITIES.glob("*/activity.json"):
        act = variants.activity(f.parent.name)
        for module_id, variant_id in (act.get("variants") or {}).items():
            assert variant_id in variants.all_variants().get(module_id, {}), (f.parent.name, module_id, variant_id)


def test_variant_fields_are_well_formed():
    for module_id, vs in variants.all_variants().items():
        for variant_id, v in vs.items():
            for record, items in (v.get("fields") or {}).items():
                for field in items:
                    if isinstance(field, str):
                        continue  # a planned variant's sketch
                    assert record in F.RECORDS, (module_id, variant_id, record)
                    assert F.KEY.match(field["key"]) and field.get("type", "text") in F.TYPES, (module_id, variant_id, field)



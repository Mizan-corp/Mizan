"""Step 7: Studio's site builder is a SYSTEM module of the ERP: always on, not offered, not removable."""
import pytest
from fastapi import HTTPException

from app.framework import composition
from app.framework.loader import manifest_problems, registry


def _site():
    return next(m for m in registry.get_all_manifests() if m.id == "site")


def test_the_site_builder_is_a_system_module():
    assert _site().system is True and _site().kind == "platform"
    assert "site" in composition.system_modules()
    assert set(composition.always_on()) == {"core", *composition.system_modules()}


def test_only_the_site_builder_is_system_so_far():
    assert [m.id for m in registry.get_all_manifests() if m.system] == ["site"]


@pytest.mark.parametrize("activity", [None, "retail", "general"])
def test_every_workspace_starts_with_the_system_modules(activity):
    assert "site" in composition.base_modules(activity)


def test_a_system_module_can_not_be_removed():
    import asyncio

    try:
        asyncio.run(composition.uninstall(None, None, "site", "keep", None))
    except HTTPException as e:
        assert e.status_code == 400
    else:
        raise AssertionError("a system module was removed")


def _manifest(**extra):
    return {"id": "x", "name": "x", "version": "1.0.0", "activity": "general", "kind": "platform", **extra}


def test_the_manifest_flag_is_validated():
    assert not [p for p in manifest_problems(_manifest(system=True)) if "system" in p]
    assert [p for p in manifest_problems(_manifest(system="yes")) if "system" in p]
    assert [p for p in manifest_problems({**_manifest(system=True), "kind": "business"}) if "system" in p]

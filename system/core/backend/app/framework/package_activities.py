"""Developers' activities, from reviewed packages (ADR-012).

Mizan's activities are folders (`app/activities/<id>/`); a developer's is an approved marketplace
version of an activity package. This keeps, per process, the definition of each activity listing's
current approved version (listed, or still run by a workspace), verified again like a store
install. The lookups that read activities (`variants.activity`, `variants.all_variants`,
`catalog.family_of`, positions, themes) fall back to it, so a workspace whose `tenants.sector` is
`acme.laundry` gets its menus, terms, variants and positions like any other.

Loaded at startup and re-checked every minute (a cheap query on the marketplace tables), and
reloaded at once by the process that approves a version (`refresh(force=True)`).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy import text

logger = logging.getLogger("package_activities")

CHECK_EVERY = 60  # seconds


@dataclass
class PackageActivity:
    id: str
    version: str
    developer: str
    key_id: str
    sha256: str
    manifest: dict
    activity: dict                      # what variants.activity() returns for it
    variants: dict[str, dict]           # Mizan module -> variant.json (its id is the activity's)
    modules: dict[str, object]          # own module id -> a Package for community.install
    themes: dict[str, object]           # theme id -> a Package for themes.install
    seed: list[dict] = field(default_factory=list)
    listed: bool = True
    revoked: bool = False


_defs: dict[str, PackageActivity] = {}
_stamp: tuple | None = None
_checked_at = 0.0
_lock = asyncio.Lock()
_loop_started = False


def get(activity_id: str | None) -> PackageActivity | None:
    return _defs.get(activity_id or "")


def all_defs() -> dict[str, PackageActivity]:
    return dict(_defs)


def from_package(pkg) -> PackageActivity:
    """A verified activity package's parts, in the shapes the platform's code expects."""
    from app.framework.loader import manifest_index
    from app.framework.package import Package

    files, m = pkg.files, pkg.manifest
    builtin = set(manifest_index())

    own: dict[str, object] = {}
    for mid in sorted({n.split("/")[1] for n in files if n.startswith("modules/")}):
        mm = json.loads(files[f"modules/{mid}/manifest.json"])
        prefix = f"modules/{mid}/entities/"
        entities = {n[len(prefix):-5]: json.loads(b) for n, b in files.items() if n.startswith(prefix)}
        own[mid] = Package(manifest={**mm, "kind": "community"}, entities=entities, files={},
                           developer=pkg.developer, key_id=pkg.key_id, sha256=pkg.sha256)

    variants = {}
    for name in sorted(n for n in files if n.startswith("variants/")):
        module = name.split("/")[1]
        variants[module] = {**json.loads(files[name]), "id": m["id"], "module": module, "status": "active", "_package": m["id"]}

    themes: dict[str, object] = {}
    for tname in sorted({n.split("/")[1] for n in files if n.startswith("themes/")}):
        prefix = f"themes/{tname}/"
        t = json.loads(files[prefix + "theme.json"])
        assets = {n[len(prefix):]: b for n, b in files.items() if n.startswith(prefix) and n != prefix + "theme.json"}
        themes[t["id"]] = Package(manifest={**t, "kind": "theme", "activity": m["id"]}, entities={}, files=assets,
                                  developer=pkg.developer, key_id=pkg.key_id, sha256=pkg.sha256)

    seed = [json.loads(b) for n, b in sorted(files.items()) if n.startswith("seed/")]
    activity = {
        **{k: v for k, v in m.items() if k not in ("modules", "optional")},
        "modules": [x for x in m.get("modules") or [] if x in builtin],
        "optional": [x for x in m.get("optional") or [] if x in builtin],
        "own_modules": [x for x in (m.get("modules") or []) + (m.get("optional") or []) if x in own],
        "variants": {module: m["id"] for module in variants},
        "source": "package",
        "developer": pkg.developer,
    }
    return PackageActivity(id=m["id"], version=m["version"], developer=pkg.developer, key_id=pkg.key_id, sha256=pkg.sha256,
                           manifest=m, activity=activity, variants=variants, modules=own, themes=themes, seed=seed)


def _caches_changed() -> None:
    """Clear what was built from the activities (they read this module)."""
    from app.framework import screens, variants
    from app.platform.permissions import positions

    for fn in (variants.activity, variants.all_variants, screens.catalogue, positions.activity_of, positions.declared_positions):
        fn.cache_clear()
    positions._standard_positions_synced = False  # their positions are written again


async def _read_stamp(db) -> tuple:
    row = (await db.execute(text(
        "SELECT (SELECT count(*) FROM marketplace_versions WHERE kind = 'activity' AND status = 'approved'),"
        " (SELECT max(reviewed_at) FROM marketplace_versions WHERE kind = 'activity'),"
        " (SELECT max(updated_at) FROM marketplace_items WHERE kind = 'activity'),"
        " (SELECT count(*) FROM developer_keys WHERE revoked_at IS NOT NULL)"))).one()
    return tuple(row)


async def refresh(force: bool = False) -> None:
    """Reload the definitions if the marketplace changed (always with `force`). Runs in a session
    of its own with no workspace bound: these are platform rows."""
    global _defs, _stamp, _checked_at
    from app.db.base import AsyncSessionLocal

    async with _lock:
        _checked_at = time.monotonic()
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
                stamp = await _read_stamp(db)
                if not force and stamp == _stamp:
                    return
                rows = (await db.execute(text("""
                    SELECT i.id, i.status, v.package, v.countersignature
                    FROM marketplace_items i
                    JOIN marketplace_versions v ON v.item_id = i.id AND v.version = i.current_version AND v.status = 'approved'
                    WHERE i.kind = 'activity'
                      AND (i.status = 'listed' OR i.id IN (SELECT DISTINCT sector FROM tenants))"""))).all()
                defs = {}
                for item_id, status, package, seal in rows:
                    d = await _verified(db, item_id, package, seal)
                    if d:
                        d.listed = status == "listed"
                        defs[item_id] = d
        except Exception as e:  # the tables may not exist yet (before migrations); keep what we had
            logger.warning("Couldn't load developers' activities: %s", e)
            return
        _defs, _stamp = defs, stamp
        _caches_changed()


async def _verified(db, item_id: str, package: bytes, seal: str | None) -> PackageActivity | None:
    from app.framework import package as mzm
    from app.platform.developers.service import key_revoked
    from app.platform.licensing import keys
    from app.platform.marketplace.listings import COUNTERSIGN_PREFIX

    try:
        pkg = mzm.verify(bytes(package))
        s = keys.verify(seal or "", prefix=COUNTERSIGN_PREFIX)
        if s.get("sha256") != pkg.sha256 or s.get("item") != item_id or pkg.kind != "activity":
            raise mzm.PackageError("the countersignature doesn't match")
        d = from_package(pkg)
    except (mzm.PackageError, keys.LicenceError, KeyError, ValueError) as e:
        logger.warning("Activity %s doesn't verify: %s", item_id, e)
        return None
    d.revoked = await key_revoked(db, pkg.key_id)
    return d


async def ensure_fresh() -> None:
    """Re-check if the last check is over a minute old (request paths that need current data)."""
    if time.monotonic() - _checked_at > CHECK_EVERY:
        await refresh()


def start() -> None:
    """Load now and keep checking, once per process (several apps share one process, ADR-011)."""
    global _loop_started
    if _loop_started:
        return
    _loop_started = True

    async def loop():
        await refresh(force=True)
        while True:
            await asyncio.sleep(CHECK_EVERY)
            await refresh()

    asyncio.get_running_loop().create_task(loop())

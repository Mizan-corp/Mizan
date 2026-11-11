"""Positions: job titles, separate from roles; a position suggests roles (ADR-006 D4).

Three layers, like the rest of the platform:
- general: positions every business has (app/activities/general/positions.json);
- the activity's own (app/activities/<activity>/positions.json): a pharmacy has pharmacists, a
  restaurant chefs and waiters, a hospital its medical staff;
- the workspace's own (tenant_id set).

Standard positions are rows with no workspace, keyed by (activity, code). A user has at most one
position (user_positions). A position only pre-ticks its suggested roles; roles decide access.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ACTIVITIES = Path(__file__).resolve().parents[2] / "activities"


@lru_cache(maxsize=1)
def declared_positions() -> dict[str, list[dict]]:
    """activity id -> its positions ({code, name, name_en, suggested_roles})."""
    out = {}
    for f in sorted(ACTIVITIES.glob("*/positions.json")):
        out[f.parent.name] = json.loads(f.read_text(encoding="utf-8"))
    return out


@lru_cache(maxsize=None)
def activity_of(sector: str | None) -> str | None:
    """A workspace's activity, following legacy activities to the one they map to."""
    if not sector:
        return None
    f = ACTIVITIES / sector / "activity.json"
    if not f.is_file():
        return None
    return json.loads(f.read_text(encoding="utf-8")).get("legacy_of") or sector


def suggested_roles(activity: str, code: str) -> list[str]:
    for p in declared_positions().get(activity, []):
        if p["code"] == code:
            return list(p.get("suggested_roles", []))
    return []


_standard_positions_synced = False


async def ensure_standard_positions() -> None:
    """Standard positions match the files (once per process, in a session of its own with no
    workspace bound: they are platform rows a request's workspace role can't write, #112)."""
    global _standard_positions_synced
    if _standard_positions_synced:
        return
    from app.db.base import AsyncSessionLocal
    from app.platform.tenancy.context import current_tenant_id

    token = current_tenant_id.set(None)
    try:
        async with AsyncSessionLocal() as own:
            await own.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            for activity, items in declared_positions().items():
                for p in items:
                    await own.execute(text("""
                        INSERT INTO org_positions (id, tenant_id, activity, code, name, name_en, category, is_active)
                        VALUES (gen_random_uuid(), NULL, :a, :code, :name, :name_en, :a, true)
                        ON CONFLICT (activity, code) WHERE tenant_id IS NULL
                        DO UPDATE SET name = EXCLUDED.name, name_en = EXCLUDED.name_en, is_active = true
                    """), {"a": activity, "code": p["code"], "name": p["name"], "name_en": p["name_en"]})
            await own.commit()
    finally:
        current_tenant_id.reset(token)
    _standard_positions_synced = True


async def list_positions(db: AsyncSession, sector: str | None) -> list[dict]:
    """General positions, the workspace's activity's, then the workspace's own, each with the
    standard role codes it suggests."""
    await ensure_standard_positions()
    activity = activity_of(sector)
    rows = (await db.execute(text("""
        SELECT id, code, name, name_en, activity, tenant_id IS NULL AS standard
        FROM org_positions
        WHERE is_active AND (tenant_id IS NOT NULL OR activity = 'general' OR activity = :a)
        ORDER BY tenant_id NULLS FIRST, (activity = 'general'), name
    """), {"a": activity or ""})).mappings().all()
    return [{**dict(r), "suggested_roles": suggested_roles(r["activity"], r["code"]) if r["standard"] else []}
            for r in rows]


async def set_position(db: AsyncSession, user, position_id) -> None:
    """The user's one position (None clears it)."""
    await db.execute(text("DELETE FROM user_positions WHERE user_id = :u"), {"u": user.id})
    if position_id is not None:
        await db.execute(text("""
            INSERT INTO user_positions (id, user_id, position_id, is_primary, tenant_id)
            VALUES (gen_random_uuid(), :u, :p, true, :t)
        """), {"u": user.id, "p": position_id, "t": user.tenant_id})

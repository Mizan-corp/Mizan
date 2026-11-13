"""Hooks: extension points where a variant adds rules without editing the module (ADR-006 D1).

A module names its points in its own `hooks.py` (POINTS) and calls `emit("pos.before_confirm",
db, ...)` at that moment. The workspace's variant for that module (from its activity) runs the
function of the same name in its variant's `hooks.py` (`activities/<activity>/variants/<module>/`,
or the module's own `variants/standard/`), if it has one. Only that
variant runs, so a pharmacy's rules never touch a restaurant's sales.

A hook may raise HTTPException to refuse the action, and may return a value (collected in order).
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework import variants


async def workspace_activity(db: AsyncSession) -> str | None:
    """The bound workspace's activity (its `sector`)."""
    from app.platform.tenancy.context import current_tenant_id

    tid = current_tenant_id.get()
    if tid is None:
        return None
    return await db.scalar(text("SELECT sector FROM tenants WHERE id = :t"), {"t": tid})


def _hooks_module(module_id: str, variant_id: str):
    data = variants.all_variants().get(module_id, {}).get(variant_id)
    if not data or not (Path(data["_dir"]) / "hooks.py").is_file():
        return None
    app_root = Path(__file__).resolve().parents[1]
    dotted = ".".join(("app", *(Path(data["_dir"]).relative_to(app_root).parts), "hooks"))
    return importlib.import_module(dotted)


async def emit(point: str, db: AsyncSession, activity_id: str | None = None, **ctx: Any) -> list:
    """Run `point` ("<module>.<moment>") for the workspace's variant of that module."""
    module_id, _, moment = point.partition(".")
    if activity_id is None:
        activity_id = await workspace_activity(db)
    variant_id = variants.variant_of(module_id, activity_id)
    if variant_id == "standard":
        return []
    hooks = _hooks_module(module_id, variant_id)
    fn = getattr(hooks, moment, None) if hooks else None
    if fn is None:
        return []
    result = fn(db, activity_id=activity_id, **ctx)
    if inspect.isawaitable(result):
        result = await result
    return [result]

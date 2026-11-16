"""Events: one module tells the workspace's other modules that something happened (ADR-014 D3).

Hooks (`framework/hooks.py`) let an activity's variant change how a module works. Events go the
other way: a module announces a business fact ("sale.confirmed", "expense.approved") without
knowing who cares, and every *active* module of the workspace that listens to it reacts, in the
same transaction. The accounting module posts its journal entries this way, so sales, POS and
finance never import it.

A module listens by having a `listeners.py` with
    LISTENERS = {"sale.confirmed": on_sale_confirmed, ...}
where each listener is `async def fn(db, **ctx)`. A listener may raise (an HTTPException or a
BusinessError) to refuse the change: the caller's transaction is then rolled back as a whole.
Modules that aren't active in the workspace never run.
"""
from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@lru_cache(maxsize=1)
def _listeners() -> dict[str, list[tuple[str, Callable]]]:
    """Event → [(module id, listener)], from every module's listeners.py."""
    from app.framework.loader import module_dirs

    app_root = Path(__file__).resolve().parents[1]
    out: dict[str, list[tuple[str, Callable]]] = {}
    for module_id, path in sorted(module_dirs().items()):
        if not (path / "listeners.py").is_file():
            continue
        dotted = ".".join(("app", *path.relative_to(app_root).parts, "listeners"))
        mod = importlib.import_module(dotted)
        for event, fn in (getattr(mod, "LISTENERS", None) or {}).items():
            out.setdefault(event, []).append((module_id, fn))
    return out


def listeners_of(event: str) -> list[str]:
    """The modules that listen to `event` (active or not)."""
    return [mid for mid, _ in _listeners().get(event, [])]


async def notify(event: str, db: AsyncSession, **ctx: Any) -> None:
    """Run the listeners of `event` of the workspace's active modules, in the caller's transaction."""
    subscribed = _listeners().get(event)
    if not subscribed:
        return
    from app.framework.activation import get_active_modules
    from app.platform.tenancy.context import current_tenant_id

    if current_tenant_id.get() is None:
        return
    active = set(await get_active_modules(db))
    for module_id, fn in subscribed:
        if module_id not in active:
            continue
        result = fn(db, **ctx)
        if inspect.isawaitable(result):
            await result

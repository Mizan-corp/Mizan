"""Theme packs (ADR-010 D3): what a workspace can choose from, and its one theme.

Sources, in the order they're listed:
- Mizan's themes: app/themes/<id>/theme.json (every workspace);
- activities' themes: activities/<activity>/themes/<id>/theme.json (workspaces of that activity;
  general's for all);
- theme packages installed in the workspace (workspace_themes), signed by a developer.

The workspace's theme is tenants.palette["name"] (kept with the brand hue the app already reads);
its admin chooses it (themes.manage) and everyone in the workspace sees it.
"""
from __future__ import annotations

import base64
import json
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.manifest import theme_problems
from app.platform.themes.models import WorkspaceTheme

APP_DIR = Path(__file__).resolve().parents[2]
DEFAULT = "mizan"
FONT_TYPES = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
              ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp", ".jpg": "image/jpeg"}


@lru_cache(maxsize=1)
def file_themes() -> dict[str, dict]:
    """Mizan's and activities' themes: id -> theme (with "source", "activity" and "_dir")."""
    out: dict[str, dict] = {}
    for f in sorted((APP_DIR / "themes").glob("*/theme.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        out[t["id"]] = {**t, "source": "mizan", "activity": None, "_dir": str(f.parent)}
    for f in sorted((APP_DIR / "activities").glob("*/themes/*/theme.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        out[t["id"]] = {**t, "source": "activity", "activity": f.parents[2].name, "_dir": str(f.parent)}
    return out


def _activity_of(tenant) -> str:
    from app.framework.variants import activity

    return activity(tenant.sector).get("id") or tenant.sector or "general"


async def available(db: AsyncSession, tenant) -> list[dict]:
    """Every theme this workspace may use: Mizan's, its activity's (and general's), its packages."""
    act = _activity_of(tenant)
    out = [t for t in file_themes().values() if t["activity"] in (None, "general", act)]
    rows = (await db.execute(select(WorkspaceTheme).where(WorkspaceTheme.tenant_id == tenant.id)
                             .order_by(WorkspaceTheme.installed_at))).scalars()
    out += [{**r.theme, "source": "package", "developer": r.developer, "activity": None} for r in rows]
    return out


def current_id(tenant) -> str:
    return (tenant.palette or {}).get("name") or DEFAULT


def _for_client(t: dict, tenant_id) -> dict:
    """What the app applies: the theme without server paths, with where its files are served."""
    out = {k: v for k, v in t.items() if not k.startswith("_")}
    files = (t.get("fonts") or {}).get("files") or []
    if files:
        if t["source"] == "package":
            out["assets_base"] = f"/themes/assets/{tenant_id}/{t['id']}/"
        else:
            out["assets_base"] = f"/themes/assets/files/{t['id']}/"
    return out


async def resolved(db: AsyncSession, tenant) -> dict:
    """The workspace's theme, ready for the app (Mizan's default when it's gone)."""
    wanted = current_id(tenant)
    for t in await available(db, tenant):
        if t["id"] == wanted:
            return _for_client(t, tenant.id)
    return _for_client(file_themes()[DEFAULT], tenant.id)


def summary(t: dict, current: str) -> dict:
    light = (t.get("colors") or {}).get("light") or {}
    return {"id": t["id"], "name": t.get("name"), "name_en": t.get("name_en"), "description": t.get("description") or "",
            "version": t.get("version"), "source": t["source"], "developer": t.get("developer"),
            "activity": t.get("activity"), "current": t["id"] == current,
            "swatches": [light.get(k) for k in ("primary", "background", "sidebar", "accent", "card") if light.get(k)],
            "fonts": t.get("fonts") or {}, "radius": t.get("radius"), "motion": t.get("motion", "full")}


async def choose(db: AsyncSession, tenant, theme_id: str) -> dict:
    """Make `theme_id` the workspace's theme."""
    from app.catalog.sectors import PALETTE_HUES

    if not any(t["id"] == theme_id for t in await available(db, tenant)):
        raise HTTPException(404, "المظهر غير متاح لهذه المنشأة")
    palette = dict(tenant.palette or {})
    palette["name"] = theme_id
    palette["hue"] = PALETTE_HUES.get(theme_id, palette.get("hue") or PALETTE_HUES[DEFAULT])
    tenant.palette = palette
    await db.commit()
    return await resolved(db, tenant)


# ── Theme packages ─────────────────────────────────────────────────────────────

def package_summary(pkg, installed: WorkspaceTheme | None) -> dict:
    t = {**pkg.manifest, "source": "package", "developer": pkg.developer}
    return {**summary(t, ""), "installed_version": installed.version if installed else None,
            "files": sorted(n for n in pkg.files if n.startswith("assets/"))}


async def installed_row(db: AsyncSession, tenant_id, theme_id: str) -> WorkspaceTheme | None:
    return await db.scalar(select(WorkspaceTheme).where(WorkspaceTheme.tenant_id == tenant_id,
                                                        WorkspaceTheme.theme_id == theme_id))


async def install(db: AsyncSession, tenant, pkg, user_id) -> WorkspaceTheme:
    if pkg.kind != "theme":
        raise HTTPException(422, "هذه الحزمة ليست مظهرًا")
    if pkg.manifest["id"] in file_themes():
        raise HTTPException(409, "يوجد مظهر بهذا المعرّف بالفعل")
    row = await installed_row(db, tenant.id, pkg.manifest["id"])
    if row is None:
        row = WorkspaceTheme(tenant_id=tenant.id, theme_id=pkg.manifest["id"])
        db.add(row)
    row.version, row.developer, row.theme = pkg.manifest["version"], pkg.developer, pkg.manifest
    row.assets = {n: base64.b64encode(b).decode() for n, b in pkg.files.items() if n.startswith("assets/")}
    row.package_sha256, row.installed_by = pkg.sha256, user_id
    await db.commit()
    return row


async def uninstall(db: AsyncSession, tenant, theme_id: str) -> None:
    row = await installed_row(db, tenant.id, theme_id)
    if row is None:
        raise HTTPException(404, "المظهر غير مثبت")
    if current_id(tenant) == theme_id:
        raise HTTPException(409, "هذا مظهر المنشأة الحالي؛ اختر غيره أولًا")
    await db.delete(row)
    await db.commit()


# ── Font files ─────────────────────────────────────────────────────────────────

def file_asset(theme_id: str, path: str) -> tuple[bytes, str]:
    t = file_themes().get(theme_id)
    if t is None or path not in [f.get("src") for f in (t.get("fonts") or {}).get("files") or []]:
        raise HTTPException(404, "Not found")
    f = Path(t["_dir"]) / path
    if not f.is_file():
        raise HTTPException(404, "Not found")
    return f.read_bytes(), FONT_TYPES.get(f.suffix.lower(), "application/octet-stream")


async def package_asset(db: AsyncSession, tenant_id: uuid.UUID, theme_id: str, path: str) -> tuple[bytes, str]:
    """A theme package's file; read across workspaces (fonts are public, like the login page)."""
    from sqlalchemy import text

    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    row = await db.scalar(select(WorkspaceTheme).where(WorkspaceTheme.tenant_id == tenant_id,
                                                       WorkspaceTheme.theme_id == theme_id))
    await db.execute(text("SELECT set_config('app.bypass', 'off', true)"))
    data = (row.assets or {}).get(path) if row else None
    if data is None:
        raise HTTPException(404, "Not found")
    return base64.b64decode(data), FONT_TYPES.get(Path(path).suffix.lower(), "application/octet-stream")


def check_file_themes() -> list[str]:
    """Problems in Mizan's and activities' theme files (for tests and `module check`)."""
    out = []
    for tid, t in file_themes().items():
        out += [f"{tid}: {p}" for p in theme_problems({k: v for k, v in t.items() if k not in ("source", "activity", "_dir")})]
        if t["activity"] and not tid.startswith(t["activity"] + "."):
            out.append(f"{tid}: an activity's theme id starts with the activity ('{t['activity']}.…')")
        for f in (t.get("fonts") or {}).get("files") or []:
            if not (Path(t["_dir"]) / str(f.get("src"))).is_file():
                out.append(f"{tid}: missing {f.get('src')}")
    return out


async def print_color(db: AsyncSession, tenant) -> str | None:
    """The theme's brand colour as #hex, for printed documents (PDF engines don't all read oklch)."""
    from app.framework.manifest import color_rgb

    primary = ((await resolved(db, tenant)).get("colors") or {}).get("light", {}).get("primary")
    rgb = color_rgb(primary) if primary else None
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb) if rgb else None

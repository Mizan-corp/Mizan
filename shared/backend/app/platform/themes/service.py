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
import logging
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.manifest import theme_problems
from app.platform.themes.models import WorkspaceTheme

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parents[2]
DEFAULT = "mizan"
FONT_TYPES = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
              ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp", ".jpg": "image/jpeg"}


FONTS_DIR = APP_DIR / "themes" / "_fonts"
PALETTES_DIR = APP_DIR / "themes" / "_palettes"


@lru_cache(maxsize=1)
def palette_registry() -> dict[str, dict]:
    """Mizan's shared palette registry: palette id -> {id, source, license, colors}.

    Theme packs reference a palette by id ("palette": "amber") instead of embedding
    the color tokens; expansion happens at load so consumers see plain "colors".
    """
    out: dict[str, dict] = {}
    if PALETTES_DIR.is_dir():
        for f in sorted(PALETTES_DIR.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            out[d["id"]] = d
    return out


@lru_cache(maxsize=1)
def font_registry() -> dict[str, dict]:
    """Mizan's shared font registry: family id -> font.json (one canonical copy per family).

    Theme packs reference families by id (fonts.files: [{"ref": "tajawal"}]) instead of
    duplicating the files; expansion happens at load so consumers see plain entries.
    """
    out: dict[str, dict] = {}
    if FONTS_DIR.is_dir():
        for f in sorted(FONTS_DIR.glob("*/font.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            d["_dir"] = str(f.parent)
            out[d["id"]] = d
    return out


def _expand_palette_ref(t: dict) -> dict:
    """A theme's "palette": "<registry id>" becomes its "colors" at load."""
    pid = t.get("palette")
    if not isinstance(pid, str) or "colors" in t:
        return t
    pal = palette_registry().get(pid)
    if pal is None:
        return t  # unresolved: theme_problems flags the missing colors
    return {**t, "colors": pal["colors"]}


def _expand_font_refs(t: dict) -> dict:
    """fonts.files entries may be {"ref": "<registry family id>"}; expand each to that
    family's plain file entries with canonical /themes/assets/fonts/ srcs."""
    fonts = t.get("fonts")
    if not isinstance(fonts, dict):
        return t
    entries = fonts.get("files")
    if not isinstance(entries, list) or not any(isinstance(e, dict) and "ref" in e for e in entries):
        return t
    registry = font_registry()
    out: list[dict] = []
    for e in entries:
        if isinstance(e, dict) and "ref" in e:
            fam = registry.get(str(e["ref"]))
            if fam:
                for fe in fam.get("files") or []:
                    out.append({"family": fam["family"], "src": f"/themes/assets/fonts/{fam['id']}/{fe['src']}",
                                "weight": fe.get("weight", "400"), "style": fe.get("style", "normal")})
            else:
                out.append(e)  # unknown ref: keep so validation can flag it
        else:
            out.append(e)
    return {**t, "fonts": {**fonts, "files": out}}


@lru_cache(maxsize=1)
def file_themes() -> dict[str, dict]:
    """Mizan's and activities' themes: id -> theme (with "source", "activity" and "_dir")."""
    out: dict[str, dict] = {}
    for f in sorted((APP_DIR / "themes").glob("*/theme.json")):
        t = _expand_palette_ref(_expand_font_refs(json.loads(f.read_text(encoding="utf-8"))))
        out[t["id"]] = {**t, "source": "mizan", "activity": None, "_dir": str(f.parent)}
    for f in sorted((APP_DIR / "activities").glob("*/themes/*/theme.json")):
        t = _expand_palette_ref(_expand_font_refs(json.loads(f.read_text(encoding="utf-8"))))
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


def family_files() -> dict[str, list[dict]]:
    """Every font family Mizan's file themes ship -> its file entries, with absolute
    srcs any theme may borrow (the files are public, like the login page)."""
    out: dict[str, list[dict]] = {}
    for t in file_themes().values():
        for f in (t.get("fonts") or {}).get("files") or []:
            fam = f.get("family")
            if isinstance(fam, str) and fam not in out:
                out[fam] = [{**f, "src": f["src"] if str(f.get("src") or "").startswith("/")
                                         else f"/themes/assets/files/{t['id']}/{f['src']}"}
                            for f in (t.get("fonts") or {}).get("files") or [] if f.get("family") == fam]
    return out


def check_font_choice(fonts) -> dict:
    """A workspace's own body/display picks (tenants.palette['fonts']); known shipped
    families only, so the resolved theme never names a face we can't serve."""
    if not isinstance(fonts, dict):
        return {}
    known = family_files()
    out = {}
    for k in ("body", "display"):
        v = fonts.get(k)
        if isinstance(v, str) and v in known:
            out[k] = v
    return out


def _with_font_choice(theme: dict, tenant) -> dict:
    """The workspace's font picks ride over its theme pack (ADR-010 D3 follow-up):
    family names plus the matching real files, borrowed from whichever pack ships them."""
    choice = (tenant.palette or {}).get("fonts")
    if not isinstance(choice, dict):
        return theme
    known = family_files()
    if not any(isinstance(choice.get(k), str) and choice[k] in known for k in ("body", "display")):
        return theme
    fonts = dict(theme.get("fonts") or {})
    files = list(fonts.get("files") or [])
    for k in ("body", "display"):
        fam = choice.get(k)
        if not (isinstance(fam, str) and fam in known):
            continue
        fonts[k] = fam
        have = {f.get("family") for f in files}
        if fam not in have:
            files += known[fam]
    if not files:
        fonts.pop("files", None)
    else:
        fonts["files"] = files
    return {**theme, "fonts": fonts}


def _with_palette_choice(theme: dict, tenant) -> dict:
    """A workspace may recolor its theme with any registry palette (ADR-010 D3 follow-up):
    tenants.palette['palette'] overrides the theme's own palette reference. Fonts, radius
    and the rest still come from the theme; the choice survives in resolved output."""
    pid = (tenant.palette or {}).get("palette")
    if not isinstance(pid, str) or not pid:
        return theme
    pal = palette_registry().get(pid)
    if pal is None:
        return theme
    return {**theme, "colors": pal["colors"], "palette": pid}


async def resolved(db: AsyncSession, tenant) -> dict:
    """The workspace's theme, ready for the app (Mizan's default when it's gone)."""
    wanted = current_id(tenant)
    for t in await available(db, tenant):
        if t["id"] == wanted:
            return _with_palette_choice(_with_font_choice(_for_client(t, tenant.id), tenant), tenant)
    return _with_palette_choice(_with_font_choice(_for_client(file_themes()[DEFAULT], tenant.id), tenant), tenant)


def summary(t: dict, current: str) -> dict:
    light = (t.get("colors") or {}).get("light") or {}
    return {"id": t["id"], "name": t.get("name"), "name_en": t.get("name_en"), "description": t.get("description") or "",
            "version": t.get("version"), "source": t["source"], "developer": t.get("developer"),
            "activity": t.get("activity"), "current": t["id"] == current,
            "swatches": [light.get(k) for k in ("primary", "background", "sidebar", "accent", "card") if light.get(k)],
            "fonts": t.get("fonts") or {}, "radius": t.get("radius"), "motion": t.get("motion", "full")}


def check_palette_choice(pid) -> str | None:
    """A workspace's own palette pick (tenants.palette['palette']): a known registry id only."""
    return pid if isinstance(pid, str) and pid in palette_registry() else None


async def choose(db: AsyncSession, tenant, theme_id: str, fonts: dict | None = None,
                 palette_id: str | None = None) -> dict:
    """Make `theme_id` the workspace's theme; optionally its own body/display faces and its
    own palette (each independent: a theme, then recolor/refont it without another theme).
    An actual edit also syncs the workspace's automatic branding profile (the owner's rule:
    modifying the pack keeps a private profile of the modifications; the pack is untouched)."""
    from app.catalog.sectors import PALETTE_HUES

    if not any(t["id"] == theme_id for t in await available(db, tenant)):
        raise HTTPException(404, "المظهر غير متاح لهذه المنشأة")
    if palette_id is not None and palette_id != "" and check_palette_choice(palette_id) is None:
        raise HTTPException(404, "لوحة الألوان غير متاحة")
    before = dict(tenant.palette or {})
    palette = dict(tenant.palette or {})
    palette["name"] = theme_id
    palette["hue"] = PALETTE_HUES.get(theme_id, palette.get("hue") or PALETTE_HUES[DEFAULT])
    if fonts is not None:
        checked = check_font_choice(fonts)
        if checked:
            palette["fonts"] = checked
        else:
            palette.pop("fonts", None)
    if palette_id is not None:
        if palette_id == "":
            palette.pop("palette", None)  # back to the theme's own palette
        else:
            palette["palette"] = palette_id
    tenant.palette = palette
    await _sync_auto_profile(db, tenant, before)
    await db.commit()
    try:
        from app.platform.site.service import refresh_activation_themes
        await refresh_activation_themes(db)
    except Exception:  # activation refresh is best-effort; sites re-snapshot on the next settings save
        logger.warning("could not refresh site activation themes after theme choice", exc_info=True)
    return await resolved(db, tenant)


# ── Automatic branding profiles (the workspace owner's rule) ─────────────────────
# Editing the theme pack automatically keeps a branding profile with the owner's
# modifications, listed in Settings > Themes and the owner panel. Profiles are
# private to that owner - never a platform-wide catalog - and the original theme
# pack stays untouched.

AUTO_PROFILE_SUFFIX = " — هوية مخصصة"


def auto_profile_name(tenant) -> str:
    """One automatic profile per workspace, named after it (the (owner, name) unique
    constraint then keeps a single row that repeated edits update in place)."""
    base = (getattr(tenant, "name", None) or "مساحة العمل").strip()
    return base[: 80 - len(AUTO_PROFILE_SUFFIX)] + AUTO_PROFILE_SUFFIX


def profile_out(p) -> dict:
    return {"id": str(p.id), "name": p.name, "theme": p.theme_id, "palette": p.palette_id,
            "fonts": p.fonts or {}}


async def _sync_auto_profile(db: AsyncSession, tenant, before: dict | None) -> None:
    """Upsert the workspace's automatic profile after an actual edit. Skipped when the
    saved config is unchanged or the workspace has no linked owner account."""
    owner_id = getattr(tenant, "owner_account_id", None)
    if owner_id is None:
        return
    after = dict(tenant.palette or {})
    if before == after:
        return
    from app.platform.auth.models.owner import OwnerBrandingProfile

    name = auto_profile_name(tenant)
    p = await db.scalar(select(OwnerBrandingProfile).where(
        OwnerBrandingProfile.owner_account_id == owner_id, OwnerBrandingProfile.name == name))
    if p is None:
        p = OwnerBrandingProfile(owner_account_id=owner_id, name=name,
                                 theme_id=after.get("name") or DEFAULT,
                                 palette_id=after.get("palette") or None,
                                 fonts=after.get("fonts") or None)
        db.add(p)
    else:
        p.theme_id = after.get("name") or DEFAULT
        p.palette_id = after.get("palette") or None
        p.fonts = after.get("fonts") or None


async def owner_profiles(db: AsyncSession, tenant) -> list[dict]:
    """The workspace owner's branding profiles, for the Settings > Themes picker. A
    workspace with no linked owner has none."""
    owner_id = getattr(tenant, "owner_account_id", None)
    if owner_id is None:
        return []
    from app.platform.auth.models.owner import OwnerBrandingProfile

    rows = (await db.execute(
        select(OwnerBrandingProfile)
        .where(OwnerBrandingProfile.owner_account_id == owner_id)
        .order_by(OwnerBrandingProfile.created_at))).scalars().all()
    return [profile_out(p) for p in rows]


async def apply_owner_profile(db: AsyncSession, tenant, profile_id: uuid.UUID) -> dict:
    """Apply one of the workspace owner's profiles from Settings > Themes. Another
    owner's profile doesn't exist from here (404, same as a missing one)."""
    from app.platform.auth.models.owner import OwnerBrandingProfile

    p = await db.scalar(select(OwnerBrandingProfile).where(
        OwnerBrandingProfile.id == profile_id,
        OwnerBrandingProfile.owner_account_id == getattr(tenant, "owner_account_id", None)))
    if p is None:
        raise HTTPException(404, "ملف الهوية غير موجود")
    return await choose(db, tenant, p.theme_id, fonts=p.fonts, palette_id=p.palette_id)


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

def font_asset(family_id: str, path: str) -> tuple[bytes, str]:
    """A registry family's file, served at /themes/assets/fonts/<family>/<file>."""
    fam = font_registry().get(family_id)
    if fam is None or path not in [f.get("src") for f in fam.get("files") or []]:
        raise HTTPException(404, "Not found")
    f = Path(fam["_dir"]) / path
    if not f.is_file():
        raise HTTPException(404, "Not found")
    return f.read_bytes(), FONT_TYPES.get(f.suffix.lower(), "application/octet-stream")


def file_asset(theme_id: str, path: str) -> tuple[bytes, str]:
    t = file_themes().get(theme_id)
    if t is None:
        raise HTTPException(404, "Not found")
    f = Path(t["_dir"]) / path
    declared = path in [e.get("src") for e in (t.get("fonts") or {}).get("files") or []]
    if f.is_file() and declared:
        return f.read_bytes(), FONT_TYPES.get(f.suffix.lower(), "application/octet-stream")
    # Legacy URL compatibility: packs no longer duplicate shared family files;
    # serve the registry's canonical copy when the basename is a known family file.
    base = Path(path).name
    for fam in font_registry().values():
        if base in [fe.get("src") for fe in fam.get("files") or []]:
            rf = Path(fam["_dir"]) / base
            if rf.is_file():
                return rf.read_bytes(), FONT_TYPES.get(rf.suffix.lower(), "application/octet-stream")
    raise HTTPException(404, "Not found")


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
    for fid, fam in font_registry().items():
        if not (Path(fam["_dir"]) / str(fam.get("license_file") or "")).is_file():
            out.append(f"_fonts/{fid}: missing license file {fam.get('license_file')}")
        for fe in fam.get("files") or []:
            if not (Path(fam["_dir"]) / str(fe.get("src"))).is_file():
                out.append(f"_fonts/{fid}: missing {fe.get('src')}")
    for f in sorted(FONTS_DIR.glob("*/theme.json")) if FONTS_DIR.is_dir() else []:
        out.append(f"_fonts: {f.parent.name} is a family directory, not a theme")
    for tid, t in file_themes().items():
        out += [f"{tid}: {p}" for p in theme_problems({k: v for k, v in t.items() if k not in ("source", "activity", "_dir", "palette")})]
        if "palette" in t and "colors" not in t:
            out.append(f"{tid}: unknown palette ref '{t.get('palette')}'")
        if t["activity"] and not tid.startswith(t["activity"] + "."):
            out.append(f"{tid}: an activity's theme id starts with the activity ('{t['activity']}.…')")
        for f in (t.get("fonts") or {}).get("files") or []:
            src = str(f.get("src"))
            if "ref" in f:
                out.append(f"{tid}: unknown font family ref '{f.get('ref')}'")
            elif src.startswith("/themes/assets/fonts/"):
                parts = src.split("/")
                try:
                    font_asset(parts[4], parts[5])
                except HTTPException:
                    out.append(f"{tid}: missing registry file {src}")
            elif src.startswith("/"):
                continue  # absolute borrow into another pack; that pack's own check covers it
            elif not (Path(t["_dir"]) / src).is_file():
                out.append(f"{tid}: missing {src}")
    return out


async def print_color(db: AsyncSession, tenant) -> str | None:
    """The theme's brand colour as #hex, for printed documents (PDF engines don't all read oklch)."""
    from app.framework.manifest import color_rgb

    primary = ((await resolved(db, tenant)).get("colors") or {}).get("light", {}).get("primary")
    rgb = color_rgb(primary) if primary else None
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb) if rgb else None

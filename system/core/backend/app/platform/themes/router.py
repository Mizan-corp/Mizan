"""Theme packs (ADR-010 D3): the workspace's theme, the themes it may use, and theme packages.
Font files are public (the login page uses the theme too)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User
from app.platform.themes import service

router = APIRouter(prefix="/themes", tags=["Themes"])
CACHE = {"Cache-Control": "public, max-age=86400"}


async def _tenant(db: AsyncSession, user: User):
    from app.platform.tenancy.models import Tenant

    return await db.get(Tenant, user.tenant_id)


class Choice(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    fonts: dict | None = None
    palette: str | None = None


@router.get("/current")
async def current(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """The workspace's theme, as the app applies it."""
    return await service.resolved(db, await _tenant(db, user))


@router.get("")
async def list_themes(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("themes.manage"))):
    tenant = await _tenant(db, user)
    now = service.current_id(tenant)
    return {"current": now, "items": [service.summary(t, now) for t in await service.available(db, tenant)]}


@router.put("/current")
async def choose(data: Choice, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("themes.manage"))):
    return await service.choose(db, await _tenant(db, user), data.id, fonts=data.fonts, palette_id=data.palette)


@router.get("/palettes")
async def list_palettes(user: User = Depends(get_current_user)):
    """Every registry palette: id + swatches + provenance, for independent recolor pickers."""
    return {"items": [
        {"id": pid, "source": p["source"], "license": p["license"],
         "swatches": [p["colors"]["light"].get(k) for k in ("primary", "accent", "background") if p["colors"]["light"].get(k)]}
        for pid, p in service.palette_registry().items()],
        "families": sorted(service.family_files().keys())}


class ProfileName(BaseModel):
    name: str = Field(min_length=2, max_length=80)


@router.get("/profiles")
async def list_profiles(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("themes.manage"))):
    """This workspace's branding profiles - the automatic one (updated on every theme edit)
    and named saves - applied here in Settings > Themes. Workspace-scoped, so the same
    behavior holds on cloud, desktop and LAN installs."""
    return {"items": await service.profiles(db, await _tenant(db, user))}


@router.post("/profiles", status_code=201)
async def save_profile(data: ProfileName, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("themes.manage"))):
    """Save the workspace's current theme + palette + fonts as a named profile."""
    return await service.save_profile(db, await _tenant(db, user), data.name)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_perm("themes.manage"))):
    await service.delete_profile(db, await _tenant(db, user), profile_id)


@router.post("/profiles/{profile_id}/apply")
async def apply_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_perm("themes.manage"))):
    """Apply one of this workspace's profiles to this workspace."""
    return await service.apply_profile(db, await _tenant(db, user), profile_id)


@router.post("/packages/inspect")
async def inspect_package(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_perm("themes.manage"))):
    from app.platform.developers.service import verify_upload

    pkg = await verify_upload(file, db, "theme")
    return service.package_summary(pkg, await service.installed_row(db, user.tenant_id, pkg.manifest["id"]))


@router.post("/packages/install")
async def install_package(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_perm("themes.manage"))):
    from app.platform.developers.service import verify_upload

    pkg = await verify_upload(file, db, "theme")
    tenant = await _tenant(db, user)
    row = await service.install(db, tenant, pkg, user.id)
    return service.summary({**row.theme, "source": "package", "developer": row.developer}, service.current_id(tenant))


@router.delete("/{theme_id}", status_code=204)
async def uninstall(theme_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("themes.manage"))):
    await service.uninstall(db, await _tenant(db, user), theme_id)


@router.get("/assets/fonts/{family_id}/{path:path}")
async def font_asset(family_id: str, path: str):
    data, kind = service.font_asset(family_id, path)
    return Response(data, media_type=kind)


@router.get("/assets/files/{theme_id}/{path:path}")
async def file_asset(theme_id: str, path: str):
    data, kind = service.file_asset(theme_id, path)
    return Response(data, media_type=kind, headers=CACHE)


@router.get("/assets/{tenant_id}/{theme_id}/{path:path}")
async def package_asset(tenant_id: uuid.UUID, theme_id: str, path: str, db: AsyncSession = Depends(get_db)):
    data, kind = await service.package_asset(db, tenant_id, theme_id, path)
    return Response(data, media_type=kind, headers=CACHE)

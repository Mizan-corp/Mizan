"""The owner's named branding profiles: save a theme plus, optionally, an independent
palette and font picks once, then apply the profile to any of the owner's workspaces.
Every query is scoped to the signed-in owner - profiles are never shared between owners."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.platform.auth.models.owner import OwnerAccount, OwnerBrandingProfile
from app.platform.auth.services.owners import get_current_owner, owned_workspace
from app.platform.themes import service as themes_service

router = APIRouter(prefix="/account/branding-profiles", tags=["branding"])


class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    theme: str = Field(min_length=2, max_length=80)
    palette: str | None = None
    fonts: dict | None = None


def _out(p: OwnerBrandingProfile) -> dict:
    return {"id": str(p.id), "name": p.name, "theme": p.theme_id, "palette": p.palette_id, "fonts": p.fonts or {}}


def _validate(data: ProfileIn) -> dict | None:
    if data.theme not in themes_service.file_themes():
        raise HTTPException(status_code=422, detail="مظهر غير معروف")
    if data.palette is not None and themes_service.check_palette_choice(data.palette) is None:
        raise HTTPException(status_code=422, detail="لوحة ألوان غير معروفة")
    fonts = themes_service.check_font_choice(data.fonts) if isinstance(data.fonts, dict) else None
    if isinstance(data.fonts, dict) and data.fonts and not fonts:
        raise HTTPException(status_code=422, detail="خطوط غير معروفة")
    return fonts


async def _owned_profile(db: AsyncSession, owner: OwnerAccount, profile_id: uuid.UUID) -> OwnerBrandingProfile:
    p = await db.scalar(
        select(OwnerBrandingProfile).where(
            OwnerBrandingProfile.id == profile_id, OwnerBrandingProfile.owner_account_id == owner.id)
    )
    if p is None:
        raise HTTPException(status_code=404, detail="ملف الهوية غير موجود")
    return p


@router.get("")
async def list_profiles(db: AsyncSession = Depends(get_db), owner: OwnerAccount = Depends(get_current_owner)):
    rows = (await db.execute(
        select(OwnerBrandingProfile)
        .where(OwnerBrandingProfile.owner_account_id == owner.id)
        .order_by(OwnerBrandingProfile.created_at))).scalars().all()
    return {"items": [_out(p) for p in rows]}


@router.post("", status_code=201)
async def create_profile(data: ProfileIn, db: AsyncSession = Depends(get_db),
                         owner: OwnerAccount = Depends(get_current_owner)):
    fonts = _validate(data)
    name = data.name.strip()
    dupe = await db.scalar(
        select(OwnerBrandingProfile.id).where(
            OwnerBrandingProfile.owner_account_id == owner.id, OwnerBrandingProfile.name == name)
    )
    if dupe is not None:
        raise HTTPException(status_code=409, detail="اسم الملف مستخدم بالفعل")
    p = OwnerBrandingProfile(owner_account_id=owner.id, name=name, theme_id=data.theme,
                             palette_id=data.palette or None, fonts=fonts or None)
    db.add(p)
    await db.commit()
    return _out(p)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         owner: OwnerAccount = Depends(get_current_owner)):
    p = await _owned_profile(db, owner, profile_id)
    await db.delete(p)
    await db.commit()


@router.post("/{profile_id}/apply/{tenant_id}")
async def apply_profile(profile_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        owner: OwnerAccount = Depends(get_current_owner)):
    """Apply one of the owner's profiles to one of the owner's workspaces."""
    p = await _owned_profile(db, owner, profile_id)
    tenant = await owned_workspace(db, owner, tenant_id)
    theme = await themes_service.choose(db, tenant, p.theme_id, fonts=p.fonts, palette_id=p.palette_id)
    await db.commit()
    return {"profile": _out(p), "theme": theme}

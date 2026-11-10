"""Public tenant resolution used by the system app to bootstrap a workspace
from its URL slug, custom domain or storefront slug."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.sectors import SECTOR_PRIMARY_MODULES, SECTOR_PRIMARY_ROUTES
from app.db.base import get_db
from app.models.settings import StoreSetting
from app.models.tenant import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/resolve/{slug_or_domain}")
async def resolve_tenant_slug(slug_or_domain: str, db: AsyncSession = Depends(get_db)):
    """Resolves a tenant by slug (e.g. 'monset-gym') or custom domain (e.g. 'erp.monset-gym.com').
    Returns basic company routing profile, active modules, and palette for client app bootstrap.
    """
    clean_identifier = slug_or_domain.strip().lower()
    if not clean_identifier or clean_identifier in ("undefined", "null", "none"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="المعرف المطلوب غير صالح",
        )
    stmt = select(Tenant).where(
        (func.lower(Tenant.slug) == clean_identifier)
        | (func.lower(Tenant.custom_domain) == clean_identifier)
        | (func.lower(Tenant.storefront_slug) == clean_identifier)
    )
    tenant = (await db.execute(stmt)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"المنشأة ذات المعرف '{slug_or_domain}' غير موجودة في ميزان",
        )


    active_mods = tenant.active_modules
    if not active_mods or active_mods == ["pos", "inventory"]:
        active_mods = SECTOR_PRIMARY_MODULES.get(tenant.sector, ["pos", "inventory", "finance"])

    primary_route = SECTOR_PRIMARY_ROUTES.get(tenant.sector, "/pos")

    s_rows = (await db.execute(
        select(StoreSetting).where(
            StoreSetting.tenant_id == tenant.id,
            StoreSetting.key.in_([
                "store_name",
                "logo_url",
                "login_title",
                "login_subtitle",
                "login_cover_url",
                "login_support_contact",
                "theme_primary",
                "theme_color",
                "login_show_powered_by",
            ])
        )
    )).scalars().all()
    s_map = {row.key: row.value for row in s_rows}

    login_config = {
        "company_name": s_map.get("store_name") or tenant.name,
        "logo_url": s_map.get("logo_url") or (tenant.palette or {}).get("logo_url"),
        "login_title": s_map.get("login_title") or (tenant.palette or {}).get("login_title"),
        "login_subtitle": s_map.get("login_subtitle") or (tenant.palette or {}).get("login_subtitle"),
        "cover_url": s_map.get("login_cover_url") or (tenant.palette or {}).get("login_cover_url"),
        "support_contact": s_map.get("login_support_contact") or (tenant.palette or {}).get("support_contact"),
        "primary_color": s_map.get("theme_primary") or s_map.get("theme_color") or (tenant.palette or {}).get("primary"),
        "show_powered_by": s_map.get("login_show_powered_by", "true") != "false",
    }

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "custom_domain": tenant.custom_domain,
        "business_type": tenant.business_type,
        "sector": tenant.sector,
        "primary_route": primary_route,
        "status": tenant.status,
        "plan": tenant.plan,
        "palette": tenant.palette,
        "deployment_mode": tenant.deployment_mode,
        "active_modules": active_mods,
        "limits": tenant.limits,
        "login_config": login_config,
    }



"""Creating a workspace: one path for website signup, the admin panel and the
owner panel, so every new workspace gets the same modules, settings and owner."""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import canonical_activity, canonical_modules
from app.core.modules import SECTOR_TO_PRESET, set_active_modules
from app.core.plans import PLANS_CONFIG, get_plan_limits
from app.core.sectors import PALETTE_HUES, SECTOR_PRIMARY_MODULES, SECTORS, TRIAL_DAYS
from app.core.tenancy import bind_tenant
from app.models.owner import OwnerAccount
from app.models.tenant import Tenant
from app.models.user import User
from app.services.demo_seed import seed_demo


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:40]
    return slug if len(slug) >= 3 else f"workspace-{uuid.uuid4().hex[:6]}"


async def unique_slug(db: AsyncSession, wanted: str | None, name: str) -> str:
    """`wanted` must be free (409 otherwise); without it, derive one from the name."""
    slug = (wanted or "").strip("-") or slugify(name)
    base, n = slug, 1
    while await db.scalar(select(Tenant.id).where(Tenant.slug == slug)):
        if wanted:
            raise HTTPException(status_code=409, detail="Another workspace already uses this URL name")
        n += 1
        slug = f"{base}-{n}"
    return slug


async def create_workspace(
    db: AsyncSession,
    *,
    name: str,
    sector: str,
    scale: str,
    admin_username: str | None,
    admin_full_name: str | None,
    admin_password_hash: str | None,
    owner: OwnerAccount | None = None,
    deployment_mode: str = "cloud_saas",
    plan: str = "trial",
    trial_days: int = TRIAL_DAYS,
    slug: str | None = None,
    palette: str = "mizan",
    features: list[str] | None = None,
    demo_data: bool = True,
) -> tuple[Tenant, User | None]:
    """Create a workspace and its first admin. With `owner`, the workspace and
    admin are linked to that owner account. Leaves the session bound to the new
    workspace; the caller commits.

    Single-device and LAN workspaces (`deployment_mode` desktop/lan) are only
    registered here, with their licence: no users and no data, because the
    workspace itself is created on the customer's machine by the installer."""
    from app.platform.licensing.services.licences import MODES, ON_PREMISE, ensure_licence

    if deployment_mode not in MODES:
        raise HTTPException(status_code=422, detail="Unknown deployment mode")
    sector = canonical_activity(sector)
    if sector not in SECTORS:
        raise HTTPException(status_code=422, detail="نشاط غير معروف")
    if plan not in PLANS_CONFIG:
        raise HTTPException(status_code=422, detail="Unknown plan")

    features = features or []
    modules = canonical_modules(SECTOR_PRIMARY_MODULES.get(sector, ["pos", "inventory", "finance"]) + features)
    tenant = Tenant(
        id=uuid.uuid4(),
        name=name.strip(),
        slug=await unique_slug(db, slug, name),
        sector=sector,
        business_type=sector,
        scale=scale,
        palette={"name": palette, "hue": PALETTE_HUES.get(palette, PALETTE_HUES["mizan"])},
        features=features,
        active_modules=modules,
        status="active",
        deployment_mode=deployment_mode,
        plan=plan,
        limits=get_plan_limits(plan),
        trial_ends_at=datetime.now(UTC) + timedelta(days=trial_days) if plan == "trial" else None,
        owner_account_id=owner.id if owner else None,
    )
    db.add(tenant)
    await db.flush()

    if deployment_mode in ON_PREMISE:
        await ensure_licence(db, tenant)
        return tenant, None

    await bind_tenant(db, tenant.id)
    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        username=admin_username,
        full_name=admin_full_name.strip(),
        role="admin",
        is_manager=True,
        permissions=["*"],
        password_hash=admin_password_hash,
        owner_account_id=owner.id if owner else None,
    )
    db.add(admin)
    await db.flush()

    if demo_data:
        await seed_demo(db, tenant.id, admin.id, sector, scale, modules)
    await set_active_modules(db, modules, preset_id=SECTOR_TO_PRESET.get(sector))
    return tenant, admin

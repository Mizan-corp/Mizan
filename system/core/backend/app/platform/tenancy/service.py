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
from app.framework.activation import SECTOR_TO_PRESET, set_active_modules
from app.platform.billing.plans import PLANS_CONFIG, get_plan_limits
from app.catalog.sectors import PALETTE_HUES, SECTORS, TRIAL_DAYS
from app.platform.tenancy.context import bind_tenant
from app.platform.auth.models.owner import OwnerAccount
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User
from app.framework.demo import seed_workspace


# A workspace's URL name is also its subdomain (<slug>.allmizan.live, ADR-008): a DNS label that
# isn't one of the platform's own names.
RESERVED_SLUGS = frozenset({
    "www", "dev", "api", "owner-api", "web-api", "admin-api", "app", "admin", "owner", "mail", "docs", "status", "help", "support", "blog",
    "static", "assets", "cdn", "c", "login", "signup", "store", "storefront", "billing", "account",
})
SLUG_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$")


def check_slug(slug: str) -> str:
    """A URL name a workspace may take (422 otherwise)."""
    if not SLUG_LABEL.match(slug or ""):
        raise HTTPException(422, "The URL name must be 3–48 lowercase letters, digits or hyphens, not starting or ending with a hyphen")
    if slug in RESERVED_SLUGS:
        raise HTTPException(422, "This URL name is reserved; choose another")
    return slug


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:40]
    return slug if len(slug) >= 3 else f"workspace-{uuid.uuid4().hex[:6]}"


async def unique_slug(db: AsyncSession, wanted: str | None, name: str) -> str:
    """`wanted` must be free (409 otherwise); without it, derive one from the name."""
    slug = (wanted or "").strip("-") or slugify(name)
    if wanted:
        check_slug(slug)
    elif slug in RESERVED_SLUGS:
        slug = f"{slug}-workspace"
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
    colors: str | None = None,
    fonts: dict | None = None,
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
    # general's defaults + the activity's, plus chosen extras the activity allows (ADR-006 D2).
    from app.framework.composition import base_modules, installable

    modules = canonical_modules(base_modules(sector) + [f for f in canonical_modules(features) if installable(f, sector)[0]])
    # The theme (ADR-010 D3): the one chosen at signup, else the activity's default, else Mizan's.
    from app.framework.variants import activity as activity_def
    from app.platform.themes.service import file_themes

    if palette not in file_themes():
        palette = activity_def(sector).get("theme") if activity_def(sector).get("theme") in file_themes() else "mizan"
    from app.platform.themes.service import check_font_choice, check_palette_choice
    _font_choice = check_font_choice(fonts) if isinstance(fonts, dict) else {}
    _palette_choice = check_palette_choice(colors)
    tenant = Tenant(
        id=uuid.uuid4(),
        name=name.strip(),
        slug=await unique_slug(db, slug, name),
        sector=sector,
        business_type=sector,
        scale=scale,
        palette={"name": palette, "hue": PALETTE_HUES.get(palette, PALETTE_HUES["mizan"]),
                 **({"palette": _palette_choice} if _palette_choice else {}),
                 **({"fonts": _font_choice} if _font_choice else {})},
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
    from app.platform.site.models import SiteSettings
    # New workspaces follow the workspace theme and logo on their site by default;
    # any explicit site setting later wins over the inherited value. Existing sites
    # (no such row) keep their stored settings untouched.
    db.add(SiteSettings(value={"follow_workspace": True}))
    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        username=admin_username,
        full_name=admin_full_name.strip(),
        role="admin",
        is_manager=True,
        password_hash=admin_password_hash,
        owner_account_id=owner.id if owner else None,
    )
    db.add(admin)
    await db.flush()
    from app.platform.permissions.access import set_access

    await set_access(db, admin, "admin")  # the admin role: every permission, explicitly

    if demo_data:
        await seed_workspace(db, tenant.id, admin.id, sector, scale, modules)
    from app.activities.general.modules.finance.services.safes import ensure_default_safe

    await ensure_default_safe(db, tenant.id)  # expenses and receipts need a safe from the first day
    await set_active_modules(db, modules, preset_id=SECTOR_TO_PRESET.get(sector))
    return tenant, admin

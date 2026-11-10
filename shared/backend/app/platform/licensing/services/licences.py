"""Licences for single-device and LAN workspaces: create, extend, issue keys (ADR-005)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.licensing import keys as licensing
from app.platform.licensing.models import Licence
from app.platform.auth.models.owner import OwnerAccount
from app.platform.tenancy.models import Tenant

CLOUD = "cloud_saas"
ON_PREMISE = ("desktop", "lan")
MODES = (CLOUD, *ON_PREMISE)


def is_on_premise(tenant: Tenant) -> bool:
    return tenant.deployment_mode in ON_PREMISE


def status(lic: Licence | None, now: datetime | None = None) -> str:
    if lic is None:
        return "none"
    if lic.revoked_at:
        return "revoked"
    return "active" if lic.valid_until >= (now or datetime.now(UTC)) else "expired"


async def get_licence(db: AsyncSession, tenant_id: uuid.UUID) -> Licence | None:
    return await db.scalar(select(Licence).where(Licence.tenant_id == tenant_id))


async def ensure_licence(db: AsyncSession, tenant: Tenant) -> Licence | None:
    """The licence of an on-premise workspace, created on first need: valid to the
    end of the trial (or now, if the trial is already over). The caller commits."""
    if not is_on_premise(tenant):
        return None
    lic = await get_licence(db, tenant.id)
    if lic is None:
        lic = Licence(id=uuid.uuid4(), tenant_id=tenant.id, mode=tenant.deployment_mode,
                      valid_until=tenant.trial_ends_at or datetime.now(UTC))
        db.add(lic)
        await db.flush()
    return lic


async def extend_to(db: AsyncSession, tenant: Tenant, until: datetime) -> Licence | None:
    """Move the licence's end later (never earlier). Used when an invoice is paid."""
    lic = await ensure_licence(db, tenant)
    if lic is not None and until > lic.valid_until:
        lic.valid_until = until
    return lic


async def payload(db: AsyncSession, tenant: Tenant, lic: Licence) -> dict:
    owner = await db.get(OwnerAccount, tenant.owner_account_id) if tenant.owner_account_id else None
    return {
        "v": 1,
        "lid": str(lic.id),
        "workspace": {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "sector": tenant.sector,
            "scale": tenant.scale,
            "modules": list(tenant.active_modules or []),
            "palette": tenant.palette or {},
        },
        "owner": {"login": owner.login, "full_name": owner.full_name} if owner else None,
        "mode": lic.mode,
        "plan": tenant.plan,
        "limits": tenant.limits or {},
        "valid_until": lic.valid_until.astimezone(UTC).isoformat(),
        "issued_at": datetime.now(UTC).isoformat(),
    }


async def issue_key(db: AsyncSession, tenant: Tenant) -> tuple[str, Licence]:
    lic = await ensure_licence(db, tenant)
    if lic is None:
        raise licensing.LicenceError("Only single-device and LAN workspaces have licences")
    return licensing.sign(await payload(db, tenant, lic)), lic

"""Admoon Platform Control Plane Domain Service.

Encapsulates aggregate analytics, tenant lifecycle management, cloning, and diagnostics.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.sale import Sale
from app.models.tenant import Tenant
from app.models.user import User
from app.services import audit_service

UTC = timezone.utc


class AdmoonService:
    @staticmethod
    async def get_overview(db: AsyncSession) -> dict[str, Any]:
        """Aggregate KPIs across all client companies, tech stack footprints, and business sectors."""
        total_tenants = (await db.execute(select(func.count(Tenant.id)))).scalar() or 0
        active_tenants = (
            await db.execute(select(func.count(Tenant.id)).where(Tenant.status == "active"))
        ).scalar() or 0
        trial_tenants = (
            await db.execute(select(func.count(Tenant.id)).where(Tenant.status == "trial"))
        ).scalar() or 0
        suspended_tenants = (
            await db.execute(select(func.count(Tenant.id)).where(Tenant.status == "suspended"))
        ).scalar() or 0

        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
        total_sales = (await db.execute(select(func.count(Sale.id)))).scalar() or 0
        total_sales_volume = (await db.execute(select(func.coalesce(func.sum(Sale.net_total), 0)))).scalar() or 0
        total_products = (await db.execute(select(func.count(Product.id)))).scalar() or 0

        # Deployment mode breakdown
        modes_res = (
            await db.execute(select(Tenant.deployment_mode, func.count(Tenant.id)).group_by(Tenant.deployment_mode))
        ).all()
        deployment_modes = {mode or "cloud_saas": count for mode, count in modes_res}

        # Business sector breakdown
        sectors_res = (
            await db.execute(select(Tenant.business_type, func.count(Tenant.id)).group_by(Tenant.business_type))
        ).all()
        business_types = {btype or "retail": count for btype, count in sectors_res}

        # Plans breakdown
        plans_res = (await db.execute(select(Tenant.plan, func.count(Tenant.id)).group_by(Tenant.plan))).all()
        plans = {plan or "trial": count for plan, count in plans_res}

        return {
            "kpis": {
                "total_tenants": total_tenants,
                "active_tenants": active_tenants,
                "trial_tenants": trial_tenants,
                "suspended_tenants": suspended_tenants,
                "total_users": total_users,
                "total_sales": total_sales,
                "total_sales_volume_egp": float(total_sales_volume),
                "total_products": total_products,
            },
            "breakdowns": {
                "deployment_modes": deployment_modes,
                "business_types": business_types,
                "plans": plans,
            },
        }

    @staticmethod
    async def clone_tenant(
        db: AsyncSession,
        source: Tenant,
        new_name: str,
        new_slug: str,
        superadmin_id: uuid.UUID,
    ) -> Tenant:
        """Clones configuration, branding, and limits from an existing tenant."""
        cloned_id = uuid.uuid4()
        cloned = Tenant(
            id=cloned_id,
            name=new_name.strip(),
            slug=new_slug.strip(),
            sector=source.sector,
            scale=source.scale,
            business_type=source.business_type,
            status="active",
            plan=source.plan,
            palette=source.palette,
            deployment_mode=source.deployment_mode,
            tech_stack=dict(source.tech_stack or {}),
            active_modules=list(source.active_modules or []),
            limits=dict(source.limits or {}),
            trial_ends_at=datetime.now(UTC) + timedelta(days=30),
        )
        db.add(cloned)
        await db.commit()

        await audit_service.log_action(
            db,
            action="tenant_cloned",
            platform_user_id=superadmin_id,
            tenant_id=cloned_id,
            details={"source_tenant_id": str(source.id), "cloned_slug": new_slug},
        )
        return cloned

    @staticmethod
    async def reset_tenant_data(
        db: AsyncSession,
        tenant: Tenant,
        superadmin_id: uuid.UUID,
    ) -> None:
        """Resets operational transactional records while preserving structure."""
        tid = str(tenant.id)
        await db.execute(text(f"DELETE FROM sales WHERE tenant_id = '{tid}'"))
        await db.execute(text(f"DELETE FROM expenses WHERE tenant_id = '{tid}'"))
        await db.execute(text(f"DELETE FROM shifts WHERE tenant_id = '{tid}'"))
        await db.commit()

        await audit_service.log_action(
            db,
            action="tenant_reset",
            platform_user_id=superadmin_id,
            tenant_id=tenant.id,
            details={"message": "Reset operational demo data"},
        )


admoon_service = AdmoonService()

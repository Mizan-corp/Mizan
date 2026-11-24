"""Read-only legacy request/work adapters. No data movement or status rewriting.

A feature's existence does not depend on variation. Available data depends on
explicitly active source modules and the caller's independently checked grants.
"""
from dataclasses import asdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.framework.activation import get_active_modules
from app.framework.loader import registry
from app.framework.helpdesk_contract import source_work_summary
from app.activities.maintenance.modules.field_service.models import FsmWorkOrder
from app.activities.property.modules.real_estate.models import RecMaintenanceTicket

async def list_source_work(db: AsyncSession, user, limit: int = 100):
    active = set(await get_active_modules(db))
    items = []
    truncated_sources = []
    invalid_source_rows = {}
    # Both sources' existing screen contract is operations. The shared route
    # additionally requires its own work-read permission, never replaces it.
    sources = [
        ("field_service", FsmWorkOrder, ("id", "tenant_id", "order_ref", "issue_description", "status")),
        ("real_estate", RecMaintenanceTicket, ("id", "tenant_id", "ticket_ref", "description", "status")),
    ]
    for source, model, keys in sources:
        if source not in active:
            continue
        rows = (await db.execute(select(model).where(model.tenant_id == user.tenant_id)
                .order_by(model.created_at.desc(), model.id).limit(limit + 1))).scalars().all()
        if len(rows) > limit:
            truncated_sources.append(source)
        for row in rows[:limit]:
            try:
                item = asdict(source_work_summary(source, {key: getattr(row, key) for key in keys},
                                                 tenant_id=str(user.tenant_id)))
            except ValueError:
                # Legacy schemas permit blank native fields. Keep the source
                # unchanged and make incomplete coverage explicit, never 500 or
                # silently present the remaining rows as a complete list.
                invalid_source_rows[source] = invalid_source_rows.get(source, 0) + 1
                continue
            items.append(item)
    values = (await registry.get_settings(db, "helpdesk"))["values"]
    return {"work_completion_enabled": values.get("work_completion") is True, "items": items, "limit_per_source": limit,
            "source_modules": sorted(active & {source for source, _, _ in sources}),
            "read_only": True, "truncated_sources": truncated_sources,
            "invalid_source_rows": invalid_source_rows}

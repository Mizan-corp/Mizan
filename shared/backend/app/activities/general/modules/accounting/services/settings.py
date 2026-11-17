"""The workspace's accounting settings: the first month of the fiscal year and the date the ledger
starts (ADR-014 D7, D10). One row in `acc_settings`, created on first write; until then the
defaults apply (January, no start date)."""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.models import Settings

DEFAULTS = {"fiscal_year_start": 1, "start_date": None}


def _view(row: Settings | None) -> dict:
    if row is None:
        return dict(DEFAULTS)
    return {"fiscal_year_start": row.fiscal_year_start, "start_date": row.start_date}


async def _row(db: AsyncSession, tenant_id: uuid.UUID) -> Settings | None:
    return (await db.execute(select(Settings).where(Settings.tenant_id == tenant_id))).scalar_one_or_none()


async def get(db: AsyncSession, tenant_id: uuid.UUID, create: bool = False) -> dict:
    row = await _row(db, tenant_id)
    if row is None and create:
        row = Settings(id=uuid.uuid4(), tenant_id=tenant_id, fiscal_year_start=1)
        db.add(row)
        await db.flush()
    return _view(row)


async def update(db: AsyncSession, tenant_id: uuid.UUID, *, fiscal_year_start: int | None = None,
                 start_date: date | None = None) -> dict:
    row = await _row(db, tenant_id)
    if row is None:
        row = Settings(id=uuid.uuid4(), tenant_id=tenant_id, fiscal_year_start=1)
        db.add(row)
    if fiscal_year_start is not None:
        row.fiscal_year_start = fiscal_year_start
    if start_date is not None:
        row.start_date = start_date
    await db.flush()
    return _view(row)

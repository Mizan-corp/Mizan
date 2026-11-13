"""Demo data for a new workspace (ADR-006): each module seeds its own part, the activity adds its
catalogue and anything specific.

Order matters: one random generator is shared, so the same activity and size always give the same
data, and rows are flushed before others refer to them.
  1. inventory: branches, then the activity's catalogue as products
  2. contacts: customers and suppliers
  3. finance: wallets and a safe
  4. inventory: opening stock
  5. sales: two weeks of sales
  6. the activity's own seed(), if it has one (healthcare: clinic records)
Rows are marked is_demo so the owner can remove them.
"""
from __future__ import annotations

import importlib
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import activities, canonical_activity

logger = logging.getLogger("mizan.demo")
rng = random.Random(20260131)

# scale -> (branches, products, customers, suppliers, sales in 14 days)
SCALES = {
    "small": (1, 24, 6, 4, 45),
    "medium": (3, 60, 12, 7, 110),
    "large": (5, 110, 20, 10, 200),
    "growing": (3, 60, 12, 7, 110),
    "enterprise": (5, 110, 20, 10, 200),
}
FALLBACK_CATALOG_ACTIVITY = "retail"  # general goods, for activities without a catalogue of their own


@dataclass
class DemoContext:
    tenant_id: uuid.UUID
    owner_id: uuid.UUID
    activity: str
    n_branches: int
    n_products: int
    n_customers: int
    n_suppliers: int
    n_sales: int
    catalog: list
    features: Any = None
    rng: random.Random = field(default_factory=lambda: rng)
    now: datetime = field(default_factory=lambda: datetime.now(UTC))
    warehouses: list = field(default_factory=list)
    products: list = field(default_factory=list)
    customers: list = field(default_factory=list)

    @staticmethod
    def new_id() -> uuid.UUID:
        return uuid.uuid4()


def _activity_seed(activity: str):
    try:
        return importlib.import_module(f"app.activities.{activity}.seed")
    except ModuleNotFoundError:
        return None


def catalog_for(activity: str) -> list:
    """The activity's CATALOG, else its legacy target's, else the general retail catalogue."""
    for candidate in (activity, activities().get(activity, {}).get("legacy_of"), FALLBACK_CATALOG_ACTIVITY):
        module = _activity_seed(candidate) if candidate else None
        if module is not None and getattr(module, "CATALOG", None):
            return module.CATALOG
    return []


async def seed_workspace(db: AsyncSession, tenant_id: uuid.UUID, owner_id: uuid.UUID, activity: str,
                         scale: str = "medium", features: Any = None) -> None:
    from app.activities.general.modules.contacts import seed as contacts
    from app.activities.general.modules.finance import seed as finance
    from app.activities.general.modules.inventory import seed as inventory
    from app.activities.general.modules.sales import seed as sales

    activity = canonical_activity(activity)
    ctx = DemoContext(tenant_id, owner_id, activity, *SCALES.get(scale, SCALES["medium"]),
                      catalog=catalog_for(activity), features=features)
    await inventory.seed_warehouses(db, ctx)
    await inventory.seed_catalog(db, ctx)
    await contacts.seed(db, ctx)
    await finance.seed(db, ctx)
    await inventory.seed_stock(db, ctx)
    await sales.seed(db, ctx)

    extra = getattr(_activity_seed(activity), "seed", None)
    if extra:
        try:
            async with db.begin_nested():  # a failure rolls back only these rows
                await extra(db, ctx)
        except Exception:  # the workspace is still usable without the extra demo records
            logger.exception("Demo data for activity %s failed", activity)

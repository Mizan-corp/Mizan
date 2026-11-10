"""System: real database and platform health. Nothing here is estimated."""
import os
import platform
import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.migrations import MIGRATIONS
from app.dependencies import require_superadmin
from app.platform.billing.models import BillingInvoice
from app.modules.general.inventory.models.product import Product
from app.modules.general.sales.models.sale import Sale
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User

router = APIRouter(prefix="/admoon/system", tags=["admin: system"])

STARTED_AT = time.time()


@router.get("")
async def system_health(db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    t0 = time.perf_counter()
    await db.execute(text("SELECT 1"))
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    version = await db.scalar(text("SHOW server_version"))
    size_bytes = await db.scalar(text("SELECT pg_database_size(current_database())"))
    connections = await db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"))
    max_connections = await db.scalar(text("SHOW max_connections"))
    tables = await db.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"))
    rls_off = await db.scalar(text(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "JOIN information_schema.columns col ON col.table_name = c.relname AND col.column_name = 'tenant_id' "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"
    ))
    applied = set((await db.execute(text("SELECT id FROM schema_migrations"))).scalars().all())
    pending = [name for name, _ in MIGRATIONS if name not in applied]

    counts = {}
    for label, model in (("workspaces", Tenant), ("users", User), ("products", Product), ("sales", Sale),
                         ("invoices", BillingInvoice)):
        counts[label] = await db.scalar(select(func.count()).select_from(model))

    return {
        "database": {
            "version": version,
            "size_mb": round((size_bytes or 0) / 1024 / 1024, 1),
            "connections": connections,
            "max_connections": int(max_connections),
            "latency_ms": latency_ms,
            "tables": tables,
            "tenant_tables_without_rls": rls_off,
        },
        "migrations": {"total": len(MIGRATIONS), "applied": len(MIGRATIONS) - len(pending), "pending": pending},
        "records": counts,
        "service": {
            "environment": os.environ.get("APP_ENV", "development"),
            "python": platform.python_version(),
            "uptime_seconds": int(time.time() - STARTED_AT),
            "host": "vercel" if os.environ.get("VERCEL") else "docker" if os.path.exists("/.dockerenv") else "local",
        },
    }

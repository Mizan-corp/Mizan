"""Auto-healing and self-provisioning utility for Healthcare ERP suite.

Ensures healthcare tables and seed data exist seamlessly in cloud serverless
environments where upfront DDL is bypassed during lambda cold-start.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mizan.healthcare.auto_heal")

async def ensure_healthcare_tables(db: AsyncSession, tenant_slug: str | None = None):
    try:
        from app.db.migrations import apply_migrations
        from app.modules.healthcare.seeder import seed_healthcare
        logger.info("Auto-healing healthcare schema on demand...")
        await apply_migrations(db)
        await seed_healthcare(session=db, tenant_slug=tenant_slug)
        logger.info("Healthcare schema successfully auto-healed and seeded.")
    except Exception as e:
        logger.error(f"Failed to auto-heal healthcare schema: {e}", exc_info=True)

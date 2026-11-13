"""Reports: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.activities.general.modules.reporting.routes import admin_overview, export, reports

router = APIRouter()
router.include_router(reports.router)
router.include_router(admin_overview.router)
router.include_router(export.router)

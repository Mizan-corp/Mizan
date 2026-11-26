"""Sales: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.activities.general.modules.sales.routes import invoices, sales

router = APIRouter()
router.include_router(sales.router)
router.include_router(invoices.router)

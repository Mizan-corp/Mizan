"""Purchases: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.activities.general.modules.purchases.routes import purchases, suppliers

router = APIRouter()
router.include_router(purchases.router)
router.include_router(suppliers.router)

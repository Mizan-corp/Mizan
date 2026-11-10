"""Inventory: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.modules.general.inventory.routes import collections, products, stock

router = APIRouter()
router.include_router(products.router)
router.include_router(stock.router)
router.include_router(collections.router)

"""Point of sale: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.modules.general.pos.routes import scan, shifts

router = APIRouter()
router.include_router(shifts.router)
router.include_router(scan.router)

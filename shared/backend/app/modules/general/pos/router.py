"""Point of sale: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.modules.general.pos.routes import shifts

router = APIRouter()
router.include_router(shifts.router)

"""HR and payroll: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.activities.general.modules.hr.routes import hr

router = APIRouter()
router.include_router(hr.router)

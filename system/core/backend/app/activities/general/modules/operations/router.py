"""Stock operations: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.activities.general.modules.operations.routes import operations

router = APIRouter()
router.include_router(operations.router)

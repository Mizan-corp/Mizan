"""Multi-entity consolidation: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/consolidation",
    tags=["Multi-entity consolidation"],
    dependencies=[Depends(require_module("consolidation"))],
)

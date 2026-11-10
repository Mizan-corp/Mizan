"""Event scheduling and venues: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/venues",
    tags=["Event scheduling and venues"],
    dependencies=[Depends(require_module("venues"))],
)

"""Production volumes and cost allocation: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/hydrocarbon_production",
    tags=["Production volumes and cost allocation"],
    dependencies=[Depends(require_module("hydrocarbon_production"))],
)

"""Production and work orders: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/production",
    tags=["Production and work orders"],
    dependencies=[Depends(require_module("production"))],
)

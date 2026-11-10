"""Table management and floor plan: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/tables",
    tags=["Table management and floor plan"],
    dependencies=[Depends(require_module("tables"))],
)

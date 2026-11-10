"""Table management and floor plan: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/tables",
    tags=["Table management and floor plan"],
    dependencies=[Depends(require_module("tables"))],
)

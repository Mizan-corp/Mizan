"""Material requirements planning (MRP): API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/material_planning",
    tags=["Material requirements planning (MRP)"],
    dependencies=[Depends(require_module("material_planning"))],
)

"""Bill of materials: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/bill_of_materials",
    tags=["Bill of materials"],
    dependencies=[Depends(require_module("bill_of_materials"))],
)

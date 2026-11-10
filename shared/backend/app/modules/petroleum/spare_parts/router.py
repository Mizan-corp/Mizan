"""Equipment and spare parts: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/spare_parts",
    tags=["Equipment and spare parts"],
    dependencies=[Depends(require_module("spare_parts"))],
)

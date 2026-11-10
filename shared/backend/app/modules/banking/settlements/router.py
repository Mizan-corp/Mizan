"""Payments, settlement and reconciliation: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/settlements",
    tags=["Payments, settlement and reconciliation"],
    dependencies=[Depends(require_module("settlements"))],
)

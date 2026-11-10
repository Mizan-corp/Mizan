"""Trainer commissions: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/trainer_commissions",
    tags=["Trainer commissions"],
    dependencies=[Depends(require_module("trainer_commissions"))],
)

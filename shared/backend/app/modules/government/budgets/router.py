"""Budgets, controls and multi-year planning: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/budgets",
    tags=["Budgets, controls and multi-year planning"],
    dependencies=[Depends(require_module("budgets"))],
)

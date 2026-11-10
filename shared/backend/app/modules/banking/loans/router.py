"""Loans, interest and fees: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/loans",
    tags=["Loans, interest and fees"],
    dependencies=[Depends(require_module("loans"))],
)

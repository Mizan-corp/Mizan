"""Beneficiaries and citizens: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/beneficiaries",
    tags=["Beneficiaries and citizens"],
    dependencies=[Depends(require_module("beneficiaries"))],
)

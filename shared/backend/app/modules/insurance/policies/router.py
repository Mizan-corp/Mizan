"""Policies, underwriting, renewals: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/policies",
    tags=["Policies, underwriting, renewals"],
    dependencies=[Depends(require_module("policies"))],
)

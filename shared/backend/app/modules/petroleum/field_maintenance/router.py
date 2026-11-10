"""Maintenance and reliability: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/field_maintenance",
    tags=["Maintenance and reliability"],
    dependencies=[Depends(require_module("field_maintenance"))],
)

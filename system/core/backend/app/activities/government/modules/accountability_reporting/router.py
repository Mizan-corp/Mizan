"""Audit and accountability reporting: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/accountability_reporting",
    tags=["Audit and accountability reporting"],
    dependencies=[Depends(require_module("accountability_reporting"))],
)

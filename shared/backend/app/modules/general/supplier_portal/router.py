"""Supplier portal: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/supplier_portal",
    tags=["Supplier portal"],
    dependencies=[Depends(require_module("supplier_portal"))],
)

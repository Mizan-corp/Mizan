"""Regulatory reporting: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/regulatory_reporting",
    tags=["Regulatory reporting"],
    dependencies=[Depends(require_module("regulatory_reporting"))],
)

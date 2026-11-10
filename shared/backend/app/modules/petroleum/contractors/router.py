"""Contractors and service companies: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/contractors",
    tags=["Contractors and service companies"],
    dependencies=[Depends(require_module("contractors"))],
)

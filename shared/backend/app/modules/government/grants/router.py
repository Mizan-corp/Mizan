"""Grants and funding: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/grants",
    tags=["Grants and funding"],
    dependencies=[Depends(require_module("grants"))],
)

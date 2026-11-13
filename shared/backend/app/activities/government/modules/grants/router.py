"""Grants and funding: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/grants",
    tags=["Grants and funding"],
    dependencies=[Depends(require_module("grants"))],
)

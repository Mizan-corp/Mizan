"""Loyalty rewards: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/loyalty",
    tags=["Loyalty rewards"],
    dependencies=[Depends(require_module("loyalty"))],
)

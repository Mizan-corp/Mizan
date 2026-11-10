"""Delivery platforms: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/delivery",
    tags=["Delivery platforms"],
    dependencies=[Depends(require_module("delivery"))],
)

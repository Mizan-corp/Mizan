"""Integration engine and webhooks: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/webhooks",
    tags=["Integration engine and webhooks"],
    dependencies=[Depends(require_module("webhooks"))],
)

"""Subscription billing: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/subscription_billing",
    tags=["Subscription billing"],
    dependencies=[Depends(require_module("subscription_billing"))],
)

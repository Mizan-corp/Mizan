"""Tickets, capacity, scanning, pricing, refunds: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/tickets",
    tags=["Tickets, capacity, scanning, pricing, refunds"],
    dependencies=[Depends(require_module("tickets"))],
)

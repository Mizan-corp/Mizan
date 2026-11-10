"""Broker and agent commissions: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/agent_commissions",
    tags=["Broker and agent commissions"],
    dependencies=[Depends(require_module("agent_commissions"))],
)

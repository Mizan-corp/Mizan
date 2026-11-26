"""Hydrocarbon inventory and custody transfer: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/custody_transfer",
    tags=["Hydrocarbon inventory and custody transfer"],
    dependencies=[Depends(require_module("custody_transfer"))],
)

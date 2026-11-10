"""Batches and expiry (FEFO): API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/batches",
    tags=["Batches and expiry (FEFO)"],
    dependencies=[Depends(require_module("batches"))],
)

"""Procurement compliance and tendering: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/tenders",
    tags=["Procurement compliance and tendering"],
    dependencies=[Depends(require_module("tenders"))],
)

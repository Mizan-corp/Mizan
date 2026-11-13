"""Tuition fees and installments: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/tuition",
    tags=["Tuition fees and installments"],
    dependencies=[Depends(require_module("tuition"))],
)

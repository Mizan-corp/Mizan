"""Drilling and field activity: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/drilling",
    tags=["Drilling and field activity"],
    dependencies=[Depends(require_module("drilling"))],
)

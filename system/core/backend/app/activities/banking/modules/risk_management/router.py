"""Risk, exposure and authorization: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/risk_management",
    tags=["Risk, exposure and authorization"],
    dependencies=[Depends(require_module("risk_management"))],
)

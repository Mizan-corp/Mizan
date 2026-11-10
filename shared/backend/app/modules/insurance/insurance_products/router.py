"""Products and coverage: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/insurance_products",
    tags=["Products and coverage"],
    dependencies=[Depends(require_module("insurance_products"))],
)

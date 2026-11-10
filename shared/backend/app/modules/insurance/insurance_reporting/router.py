"""Insurance regulatory reporting: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/insurance_reporting",
    tags=["Insurance regulatory reporting"],
    dependencies=[Depends(require_module("insurance_reporting"))],
)

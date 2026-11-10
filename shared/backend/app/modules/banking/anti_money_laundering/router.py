"""Anti-money laundering (AML): API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/anti_money_laundering",
    tags=["Anti-money laundering (AML)"],
    dependencies=[Depends(require_module("anti_money_laundering"))],
)

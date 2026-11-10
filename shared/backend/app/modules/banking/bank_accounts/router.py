"""Customer and account master, balances: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/bank_accounts",
    tags=["Customer and account master, balances"],
    dependencies=[Depends(require_module("bank_accounts"))],
)

"""Transaction engine and immutable logs: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/bank_transactions",
    tags=["Transaction engine and immutable logs"],
    dependencies=[Depends(require_module("bank_transactions"))],
)

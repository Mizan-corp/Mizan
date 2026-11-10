"""Fund accounting and restricted funds: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/fund_accounting",
    tags=["Fund accounting and restricted funds"],
    dependencies=[Depends(require_module("fund_accounting"))],
)

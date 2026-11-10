"""Finance: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.modules.general.finance.routes import expenses, finance, ledger, periods, safes, wallets

router = APIRouter()
router.include_router(ledger.router)
router.include_router(finance.router)
router.include_router(safes.router)
router.include_router(wallets.router)
router.include_router(expenses.router)
router.include_router(periods.router)

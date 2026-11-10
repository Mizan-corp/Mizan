"""Member check-in: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/check_in",
    tags=["Member check-in"],
    dependencies=[Depends(require_module("check_in"))],
)

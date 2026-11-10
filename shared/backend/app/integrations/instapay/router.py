"""InstaPay payments: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/instapay",
    tags=["InstaPay payments"],
    dependencies=[Depends(require_module("instapay"))],
)

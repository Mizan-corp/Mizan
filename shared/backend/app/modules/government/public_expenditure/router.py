"""Public expenditure tracking: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/public_expenditure",
    tags=["Public expenditure tracking"],
    dependencies=[Depends(require_module("public_expenditure"))],
)

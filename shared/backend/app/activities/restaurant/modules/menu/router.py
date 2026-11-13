"""Menu and modifiers: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/menu",
    tags=["Menu and modifiers"],
    dependencies=[Depends(require_module("menu"))],
)

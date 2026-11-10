"""Gaming equipment and assets: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/gaming_assets",
    tags=["Gaming equipment and assets"],
    dependencies=[Depends(require_module("gaming_assets"))],
)

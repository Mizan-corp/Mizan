"""Asset management: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/assets",
    tags=["Asset management"],
    dependencies=[Depends(require_module("assets"))],
)

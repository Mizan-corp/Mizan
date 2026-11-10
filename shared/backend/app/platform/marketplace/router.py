"""Module marketplace and self-configuration: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/marketplace",
    tags=["Module marketplace and self-configuration"],
    dependencies=[Depends(require_module("marketplace"))],
)

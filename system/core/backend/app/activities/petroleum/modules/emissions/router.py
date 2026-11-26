"""Environmental and emissions reporting: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/emissions",
    tags=["Environmental and emissions reporting"],
    dependencies=[Depends(require_module("emissions"))],
)

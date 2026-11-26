"""HSE, incidents and permit-to-work: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/health_safety_environment",
    tags=["HSE, incidents and permit-to-work"],
    dependencies=[Depends(require_module("health_safety_environment"))],
)

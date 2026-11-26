"""Insurance claims: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/insurance_claims",
    tags=["Insurance claims"],
    dependencies=[Depends(require_module("insurance_claims"))],
)

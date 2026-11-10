"""Claims processing and reserves: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/claims",
    tags=["Claims processing and reserves"],
    dependencies=[Depends(require_module("claims"))],
)

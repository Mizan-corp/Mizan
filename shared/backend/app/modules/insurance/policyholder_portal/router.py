"""Policyholder portal: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/policyholder_portal",
    tags=["Policyholder portal"],
    dependencies=[Depends(require_module("policyholder_portal"))],
)

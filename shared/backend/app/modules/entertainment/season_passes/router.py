"""Memberships and season passes: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/season_passes",
    tags=["Memberships and season passes"],
    dependencies=[Depends(require_module("season_passes"))],
)

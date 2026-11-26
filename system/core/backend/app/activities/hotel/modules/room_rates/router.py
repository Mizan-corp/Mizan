"""Room rates by season: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/room_rates",
    tags=["Room rates by season"],
    dependencies=[Depends(require_module("room_rates"))],
)

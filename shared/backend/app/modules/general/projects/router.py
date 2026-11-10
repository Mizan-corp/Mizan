"""Project management: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/projects",
    tags=["Project management"],
    dependencies=[Depends(require_module("projects"))],
)

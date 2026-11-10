"""Joint venture cost allocation: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/joint_ventures",
    tags=["Joint venture cost allocation"],
    dependencies=[Depends(require_module("joint_ventures"))],
)

"""Document management: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/documents",
    tags=["Document management"],
    dependencies=[Depends(require_module("documents"))],
)

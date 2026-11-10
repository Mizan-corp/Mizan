"""Premium rating, billing and collection: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/premiums",
    tags=["Premium rating, billing and collection"],
    dependencies=[Depends(require_module("premiums"))],
)

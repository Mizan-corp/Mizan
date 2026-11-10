"""Customer portal: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/customer_portal",
    tags=["Customer portal"],
    dependencies=[Depends(require_module("customer_portal"))],
)

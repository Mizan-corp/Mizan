"""Food waste and spoilage: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/waste",
    tags=["Food waste and spoilage"],
    dependencies=[Depends(require_module("waste"))],
)

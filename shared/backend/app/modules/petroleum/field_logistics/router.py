"""Field procurement and logistics: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/field_logistics",
    tags=["Field procurement and logistics"],
    dependencies=[Depends(require_module("field_logistics"))],
)

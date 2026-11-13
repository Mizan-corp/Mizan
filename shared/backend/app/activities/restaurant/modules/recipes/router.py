"""Recipes and ingredient BOM: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/recipes",
    tags=["Recipes and ingredient BOM"],
    dependencies=[Depends(require_module("recipes"))],
)

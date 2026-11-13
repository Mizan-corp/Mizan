"""Public-sector projects: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/public_projects",
    tags=["Public-sector projects"],
    dependencies=[Depends(require_module("public_projects"))],
)

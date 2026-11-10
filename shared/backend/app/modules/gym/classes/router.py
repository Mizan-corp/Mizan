"""Classes and trainer scheduling: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/classes",
    tags=["Classes and trainer scheduling"],
    dependencies=[Depends(require_module("classes"))],
)

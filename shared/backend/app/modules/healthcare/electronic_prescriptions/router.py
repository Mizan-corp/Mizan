"""Electronic prescriptions: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/electronic_prescriptions",
    tags=["Electronic prescriptions"],
    dependencies=[Depends(require_module("electronic_prescriptions"))],
)

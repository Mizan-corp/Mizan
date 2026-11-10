"""Classes and timetable: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/timetable",
    tags=["Classes and timetable"],
    dependencies=[Depends(require_module("timetable"))],
)

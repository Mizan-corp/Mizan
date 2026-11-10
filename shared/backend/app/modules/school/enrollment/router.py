"""Admissions and enrollment: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/enrollment",
    tags=["Admissions and enrollment"],
    dependencies=[Depends(require_module("enrollment"))],
)

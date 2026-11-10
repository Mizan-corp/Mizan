"""Program and outcome performance: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/program_performance",
    tags=["Program and outcome performance"],
    dependencies=[Depends(require_module("program_performance"))],
)

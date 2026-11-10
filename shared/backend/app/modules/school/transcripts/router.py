"""Student transcripts: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/transcripts",
    tags=["Student transcripts"],
    dependencies=[Depends(require_module("transcripts"))],
)

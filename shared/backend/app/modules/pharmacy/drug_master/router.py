"""Drug master: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.core.modules import require_module

router = APIRouter(
    prefix="/modules/drug_master",
    tags=["Drug master"],
    dependencies=[Depends(require_module("drug_master"))],
)

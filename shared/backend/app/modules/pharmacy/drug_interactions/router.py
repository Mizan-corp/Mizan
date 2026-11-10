"""Drug interaction checking: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/drug_interactions",
    tags=["Drug interaction checking"],
    dependencies=[Depends(require_module("drug_interactions"))],
)

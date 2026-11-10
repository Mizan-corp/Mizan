"""Know your customer (KYC): API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/customer_verification",
    tags=["Know your customer (KYC)"],
    dependencies=[Depends(require_module("customer_verification"))],
)

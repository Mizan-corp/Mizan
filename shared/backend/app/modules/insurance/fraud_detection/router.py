"""Fraud detection and risk scoring: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/fraud_detection",
    tags=["Fraud detection and risk scoring"],
    dependencies=[Depends(require_module("fraud_detection"))],
)

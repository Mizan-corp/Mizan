"""Internationalization & Multi-language: API routes. Routes parse the request, check permissions and call service.py."""
from fastapi import APIRouter, Depends

from app.framework.activation import require_module

router = APIRouter(
    prefix="/modules/i18n",
    tags=["Internationalization & Multi-language"],
    dependencies=[Depends(require_module("i18n"))],
)

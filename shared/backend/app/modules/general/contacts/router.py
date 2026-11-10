"""Contacts: API routes. Each area is in routes/; URLs are unchanged from before ADR-006."""
from fastapi import APIRouter

from app.modules.general.contacts.routes import parties

router = APIRouter()
router.include_router(parties.router)

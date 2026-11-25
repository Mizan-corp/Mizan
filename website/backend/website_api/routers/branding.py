"""Workspace branding for the onboarding wizard: set the canonical workspace
logo right after signup with the signup access token. Same storage and
validation as the ERP settings surface; a storage outage answers 503 and saves
nothing, so the wizard can show the failure and retry the upload alone.
"""
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.auth.models.user import User
from app.platform.settings import branding

router = APIRouter(prefix="/branding", tags=["Branding"])


@router.post("/logo")
async def upload_workspace_logo(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                                user: User = Depends(get_current_user)):
    return await branding.store_workspace_logo(db, file)


@router.get("")
async def get_workspace_branding(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return {"logo_url": await branding.get_workspace_logo(db)}

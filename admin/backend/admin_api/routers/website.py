"""The public website's visit counters (ADR-016): page views, events, languages and referring
sites over the last days. Counts only; nothing identifies a visitor."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_superadmin
from app.platform.auth.models.user import User
from app.platform.site_analytics import service

router = APIRouter(prefix="/admoon/website", tags=["admin: website"])


@router.get("/analytics")
async def website_analytics(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db),
                            _: User = Depends(require_superadmin)):
    return await service.summary(db, days)

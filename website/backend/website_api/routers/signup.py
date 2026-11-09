"""Public website surface: plans and self-serve workspace signup.

A merchant signs up through the onboarding wizard → a workspace tenant is created
with a tailored demo dataset and an owner account → the owner is handed off to
the owner panel (welcome tour), on a trial.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.core.sectors import PLANS, SCALE_ALIASES, SCALES, SECTOR_PRIMARY_ROUTES, SECTORS, TRIAL_DAYS
from app.core.security import hash_password
from app.db.base import get_db
from app.models.owner import OwnerAccount
from app.models.user import User
from app.services.owners import issue_owner_token, normalize_login
from app.services.workspaces import create_workspace

logger = logging.getLogger("mizan.website.signup")

router = APIRouter(prefix="/platform", tags=["platform"])

signup_limiter = RateLimiter(max_requests=5, window_seconds=3600)


class SignupRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=128)
    sector: str
    scale: str
    palette: str = "mizan"
    features: list[str] = Field(default_factory=list)
    owner_username: str = Field(min_length=3, max_length=64, pattern=r"^[\w.\-]+$")
    owner_password: str = Field(min_length=6, max_length=128)
    owner_full_name: str = Field(min_length=2, max_length=128)
    owner_phone: str | None = Field(default=None, max_length=32)



@router.get("/plans")
async def list_plans():
    return {"plans": PLANS, "trial_days": TRIAL_DAYS}


@router.post("/signup")
async def signup(data: SignupRequest, request: Request, db: AsyncSession = Depends(get_db), _=Depends(signup_limiter)):
    norm_scale = SCALE_ALIASES.get(data.scale, data.scale)
    if data.sector not in SECTORS or (data.scale not in SCALES and norm_scale not in SCALES):
        raise HTTPException(status_code=422, detail="نشاط غير معروف")
    data.scale = norm_scale

    try:
        taken = await db.scalar(select(User.id).where(User.username == data.owner_username).limit(1)) or await db.scalar(
            select(OwnerAccount.id).where(OwnerAccount.login == normalize_login(data.owner_username))
        )
        if taken:
            raise HTTPException(status_code=409, detail="اسم المستخدم محجوز — اختر اسمًا آخر")

        password_hash = hash_password(data.owner_password)
        account = OwnerAccount(
            id=uuid.uuid4(),
            login=normalize_login(data.owner_username),
            full_name=data.owner_full_name.strip(),
            phone=data.owner_phone,
            password_hash=password_hash,
        )
        db.add(account)
        await db.flush()
        tenant, owner = await create_workspace(
            db,
            name=data.company_name,
            sector=data.sector,
            scale=data.scale,
            palette=data.palette,
            features=data.features,
            admin_username=data.owner_username,
            admin_full_name=data.owner_full_name,
            admin_password_hash=password_hash,
            owner=account,
        )
        primary_route = SECTOR_PRIMARY_ROUTES.get(data.sector, "/pos")
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Workspace creation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"فشل إنشاء مساحة العمل: {str(e)}")

    # issue a token exactly like /auth/login does
    from app.services import auth_service
    token = auth_service.issue_token(owner)
    from app.api.routers.auth import TokenResponse
    body = TokenResponse(
        access_token=token["access_token"], token_type="bearer",
        user_id=token["user_id"], username=token["username"],
        full_name=token["full_name"], role=token["role"],
    ).model_dump()
    from fastapi.responses import JSONResponse
    # The owner token opens the owner panel (the welcome tour); the ERP token
    # stays in the response for clients that go straight to the workspace.
    resp = JSONResponse(content={**body, "owner_token": issue_owner_token(account), "primary_route": primary_route, "tenant": {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "sector": tenant.sector,
        "business_type": tenant.business_type,
        "primary_route": primary_route,
        "plan": tenant.plan,
        "trial_ends_at": tenant.trial_ends_at.isoformat(),
        "palette": tenant.palette,
        "features": tenant.features,
        "active_modules": tenant.active_modules,
    }})
    # No cookie: the website never holds a session. The token is handed to the
    # system app, which signs the new owner in.
    return resp

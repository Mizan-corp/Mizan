"""Public website surface: plans and self-serve workspace signup.

A merchant signs up through the onboarding wizard → a workspace tenant is created
with a tailored demo dataset → they are handed off to the system app on a trial.
"""
import logging
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.modules import SECTOR_TO_PRESET, set_active_modules
from app.core.ratelimit import RateLimiter
from app.core.sectors import (
    PALETTE_HUES,
    PLANS,
    SCALE_ALIASES,
    SCALES,
    SECTOR_PRIMARY_MODULES,
    SECTOR_PRIMARY_ROUTES,
    SECTORS,
    TRIAL_DAYS,
)
from app.core.security import hash_password
from app.core.tenancy import bind_tenant
from app.db.base import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.services.demo_seed import seed_demo

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
        existing = await db.execute(select(User.id).where(User.username == data.owner_username))
        if existing.scalar():
            raise HTTPException(status_code=409, detail="اسم المستخدم محجوز — اختر اسمًا آخر")

        # Generate a unique URL slug for the tenant
        normalized = unicodedata.normalize("NFKD", data.company_name).encode("ascii", "ignore").decode("ascii").lower()
        cleaned = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
        candidate = cleaned[:32] if cleaned and len(cleaned) >= 3 else f"tenant-{uuid.uuid4().hex[:6]}"

        base_candidate = candidate
        suffix_counter = 1
        while True:
            exists = (await db.execute(select(Tenant.id).where(Tenant.slug == candidate))).scalar_one_or_none()
            if not exists:
                break
            candidate = f"{base_candidate}-{suffix_counter}"
            suffix_counter += 1

        tenant_slug = candidate
        hue = PALETTE_HUES.get(data.palette, 250)

        # Calculate initial active modules: sector defaults merged with requested features
        base_mods = SECTOR_PRIMARY_MODULES.get(data.sector, ["pos", "inventory", "finance"])
        requested_features = data.features or []
        all_active = list(dict.fromkeys(base_mods + requested_features))
        primary_route = SECTOR_PRIMARY_ROUTES.get(data.sector, "/pos")
        preset_id = SECTOR_TO_PRESET.get(data.sector)

        tenant = Tenant(
            id=uuid.uuid4(),
            name=data.company_name.strip(),
            slug=tenant_slug,
            sector=data.sector,
            scale=data.scale,
            palette={"name": data.palette, "hue": hue},
            features=requested_features,
            active_modules=all_active,
            status="active",
            deployment_mode="cloud_saas",
            business_type=data.sector,
            plan="trial",
            trial_ends_at=datetime.now(UTC) + timedelta(days=TRIAL_DAYS),
        )
        db.add(tenant)
        await db.flush()

        await bind_tenant(db, tenant.id)  # seed inside the tenant's context (ctx + RLS GUC)
        owner = User(
            id=uuid.uuid4(),
            username=data.owner_username,
            full_name=data.owner_full_name.strip(),
            role="admin",
            permissions=["*"],
            password_hash=hash_password(data.owner_password),
            tenant_id=tenant.id,
        )
        db.add(owner)
        await db.flush()

        await seed_demo(db, tenant.id, owner.id, data.sector, data.scale, all_active)

        # Persist the sector's active modules and preset so guards + Modules page resolve
        await set_active_modules(db, all_active, preset_id=preset_id)

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
    resp = JSONResponse(content={**body, "primary_route": primary_route, "tenant": {
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

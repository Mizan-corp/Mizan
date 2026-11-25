"""Public website surface: plans and self-serve workspace signup.

A merchant signs up through the onboarding wizard → a workspace tenant is created
with a tailored demo dataset and an owner account → the owner is handed off to
the owner panel (welcome tour), on a trial.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.catalog import canonical_activity
from app.catalog.sectors import PLANS, SCALE_ALIASES, SCALES, SECTOR_PRIMARY_ROUTES, SECTORS, TRIAL_DAYS
from app.platform.auth.security import hash_password
from app.db.base import get_db
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.models.user import User
from app.platform.auth.services.owners import issue_owner_token, normalize_login
from app.platform.tenancy.service import create_workspace

logger = logging.getLogger("mizan.website.signup")

router = APIRouter(prefix="/platform", tags=["platform"])

signup_limiter = RateLimiter(max_requests=5, window_seconds=3600)


class SignupRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=128)
    sector: str
    scale: str
    palette: str = "mizan"
    # Optional independent typography picks (body/display); validated against the
    # families Mizan's themes actually ship, stored on the workspace palette.
    fonts: dict | None = None
    features: list[str] = Field(default_factory=list)
    owner_username: str = Field(min_length=3, max_length=64, pattern=r"^[\w.\-]+$")
    owner_password: str = Field(min_length=6, max_length=128)
    owner_full_name: str = Field(min_length=2, max_length=128)
    # #72: how Mizan reaches the owner (receipts, reminders, password reset). The email is
    # verified with a code right after signup.
    owner_email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    owner_phone: str = Field(max_length=32, pattern=r"^\+?[0-9 ]{8,20}$")



@router.get("/plans")
async def list_plans():
    return {"plans": PLANS, "trial_days": TRIAL_DAYS}


@router.get("/branding")
async def branding_options():
    """What the onboarding wizard shows: Mizan's theme packs and each activity's
    branding recommendations (activity.json "branding"), so a new merchant picks
    a real, licensed palette with its own fonts instead of static swatches."""
    import json as _json

    from app.framework.variants import ACTIVITIES
    from app.platform.themes.service import file_themes, summary

    from app.platform.themes.service import _for_client

    file_packs = [t for t in file_themes().values() if t["activity"] is None]
    themes = [summary(t, "") for t in file_packs]
    full = {t["id"]: _for_client(t, None) for t in file_packs}
    recommendations: dict[str, dict] = {}
    for f in sorted(ACTIVITIES.glob("*/activity.json")):
        a = _json.loads(f.read_text(encoding="utf-8"))
        if isinstance(a.get("branding"), dict):
            recommendations[a["id"]] = a["branding"]
    from app.platform.themes.service import family_files

    fam_files = family_files()
    return {"themes": themes, "full": full, "activities": recommendations,
            "families": sorted(fam_files.keys()), "family_files": fam_files}


# The wizard previews a theme with its real fonts before signup: Mizan's file
# themes are public (the login page shows them too), served like the system's
# /themes/assets/files/... so theme.ts accepts the URL.
assets_router = APIRouter(tags=["platform"])


@assets_router.get("/themes/assets/fonts/{family_id}/{path:path}")
async def font_asset(family_id: str, path: str):
    from fastapi import Response
    from app.platform.themes import service as themes_service

    data, kind = themes_service.font_asset(family_id, path)
    return Response(data, media_type=kind)


@assets_router.get("/themes/assets/files/{theme_id}/{path:path}")
async def file_theme_asset(theme_id: str, path: str):
    from app.platform.themes import service as themes_service

    data, kind = themes_service.file_asset(theme_id, path)
    return Response(data, media_type=kind, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/signup")
async def signup(data: SignupRequest, request: Request, db: AsyncSession = Depends(get_db), _=Depends(signup_limiter)):
    norm_scale = SCALE_ALIASES.get(data.scale, data.scale)
    data.sector = canonical_activity(data.sector)
    if data.sector not in SECTORS or (data.scale not in SCALES and norm_scale not in SCALES):
        raise HTTPException(status_code=422, detail="نشاط غير معروف")
    data.scale = norm_scale

    try:
        taken = await db.scalar(select(User.id).where(User.username == data.owner_username).limit(1)) or await db.scalar(
            select(OwnerAccount.id).where(OwnerAccount.login == normalize_login(data.owner_username))
        )
        if taken:
            raise HTTPException(status_code=409, detail="اسم المستخدم محجوز — اختر اسمًا آخر")
        email = data.owner_email.strip().lower()
        if await db.scalar(select(OwnerAccount.id).where(func.lower(OwnerAccount.email) == email,
                                                         OwnerAccount.email_verified_at.is_not(None)).limit(1)):
            raise HTTPException(status_code=409, detail="هذا البريد مسجّل لحساب آخر؛ سجّل الدخول أو استعد كلمة المرور")

        password_hash = hash_password(data.owner_password)
        account = OwnerAccount(
            id=uuid.uuid4(),
            login=normalize_login(data.owner_username),
            full_name=data.owner_full_name.strip(),
            email=email,
            phone=" ".join(data.owner_phone.split()),
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
            fonts=data.fonts,
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

    # The code to verify the email (#72); signup doesn't wait on, or fail with, the mail.
    try:
        from app.platform.auth.services.owner_mail import send_code

        await send_code(db, account, "verify_email", account.email)
    except Exception as e:  # no mail service, or the provider refused: the panel offers "send again"
        logger.warning("Verification email after signup failed: %s", getattr(e, "detail", e))

    # issue a token exactly like /auth/login does
    from app.platform.auth.services import auth as auth_service
    token = auth_service.issue_token(owner)
    from app.platform.auth.routes.auth import TokenResponse
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

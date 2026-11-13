"""The developer portal's API (ADR-007 D5/D6), served at dev.allmizan.live: accounts, teams,
signing keys (certified by Mizan) and CLI tokens. Logic: app.platform.developers.service.

Authenticated with a portal session (scope "developer") or a CLI token (mzd_…):
    Authorization: Bearer <token>
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.db.base import get_db
from app.platform.developers import service
from app.platform.developers.models import DeveloperUser

async def language(request: Request) -> None:
    """English by default; Arabic when the client asks (Accept-Language: ar…)."""
    service.LANG.set("ar" if request.headers.get("accept-language", "").lower().startswith("ar") else "en")


router = APIRouter(prefix="/developers", tags=["developers"], dependencies=[Depends(language)])
_bearer = OAuth2PasswordBearer(tokenUrl="/developers/login", auto_error=False)
signup_limiter = RateLimiter(max_requests=5, window_seconds=3600)
login_limiter = RateLimiter(max_requests=20, window_seconds=600)


async def current_developer(token: str | None = Depends(_bearer), db: AsyncSession = Depends(get_db)) -> DeveloperUser:
    if not token:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return await service.user_from_token(db, token)


class SignupIn(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TeamIn(BaseModel):
    handle: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=128)


class MemberIn(BaseModel):
    email: str = Field(max_length=254)
    role: str = "member"


class KeyIn(BaseModel):
    public_key: str = Field(min_length=40, max_length=64)
    name: str = Field(default="default", max_length=64)


class CliTokenIn(BaseModel):
    name: str = Field(default="CLI", min_length=1, max_length=64)


def _me(user: DeveloperUser) -> dict:
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name}


@router.post("/signup", status_code=201)
async def signup(data: SignupIn, db: AsyncSession = Depends(get_db), _=Depends(signup_limiter)):
    user = await service.signup(db, data.email, data.full_name, data.password)
    return {"access_token": service.issue_session(user), "token_type": "bearer", "developer": _me(user)}


@router.post("/login")
async def login(data: LoginIn, db: AsyncSession = Depends(get_db), _=Depends(login_limiter)):
    user = await service.authenticate(db, data.email, data.password)
    return {"access_token": service.issue_session(user), "token_type": "bearer", "developer": _me(user)}


@router.post("/logout", status_code=204)
async def logout(db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    from app.platform.auth.sessions import revoke

    payload = getattr(user, "token_payload", None)
    if payload:
        await revoke(db, payload)
        await db.commit()


@router.get("/me")
async def me(db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    return {**_me(user), "teams": await service.teams_of(db, user)}


@router.post("/me/password", status_code=204)
async def change_password(data: PasswordIn, db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    await service.change_password(db, user, data.current_password, data.new_password)


# ── Teams ─────────────────────────────────────────────────────────────────────

@router.post("/teams", status_code=201)
async def create_team(data: TeamIn, db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    return await service.create_team(db, user, data.handle, data.name)


@router.get("/teams/{handle}")
async def team(handle: str, db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    t, role = await service.membership(db, user, handle)
    return {**service.team_out(t, role), "members": await service.members(db, t), "keys": await service.keys(db, t)}


@router.post("/teams/{handle}/members", status_code=201)
async def add_member(handle: str, data: MemberIn, db: AsyncSession = Depends(get_db),
                     user: DeveloperUser = Depends(current_developer)):
    t, _ = await service.membership(db, user, handle, owner=True)
    await service.add_member(db, t, data.email, data.role)
    return {"members": await service.members(db, t)}


@router.delete("/teams/{handle}/members/{user_id}", status_code=204)
async def remove_member(handle: str, user_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: DeveloperUser = Depends(current_developer)):
    # Owners remove anyone; a member can leave.
    t, _ = await service.membership(db, user, handle, owner=user_id != user.id)
    await service.remove_member(db, t, user_id)


# ── Signing keys ──────────────────────────────────────────────────────────────

@router.get("/teams/{handle}/keys")
async def list_keys(handle: str, db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    t, _ = await service.membership(db, user, handle)
    return {"items": await service.keys(db, t)}


@router.post("/teams/{handle}/keys", status_code=201)
async def register_key(handle: str, data: KeyIn, db: AsyncSession = Depends(get_db),
                       user: DeveloperUser = Depends(current_developer)):
    """Certify a public key for this team: the certificate `mizan package` puts in packages."""
    t, _ = await service.membership(db, user, handle)
    return await service.register_key(db, t, user, data.name, data.public_key)


@router.post("/teams/{handle}/keys/{key_id}/revoke", status_code=204)
async def revoke_key(handle: str, key_id: str, db: AsyncSession = Depends(get_db),
                     user: DeveloperUser = Depends(current_developer)):
    t, _ = await service.membership(db, user, handle, owner=True)
    await service.revoke_key(db, t, key_id)


# ── Marketplace submissions (ADR-007 milestone 2, #105) ─────────────────────────


@router.post("/teams/{handle}/packages", status_code=201)
async def submit_package(handle: str, request: Request, db: AsyncSession = Depends(get_db),
                         user: DeveloperUser = Depends(current_developer)):
    """Submit a signed package (the .mzm bytes as the body, or a multipart `file`) for review.
    `mizan publish` uses this."""
    from app.framework.package import MAX_BYTES
    from app.platform.marketplace import listings

    t, _ = await service.membership(db, user, handle)
    if (request.headers.get("content-type") or "").startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        data = await upload.read(MAX_BYTES + 1) if upload is not None and hasattr(upload, "read") else b""
    else:
        data = await request.body()
    if not data:
        raise HTTPException(422, service._("Send the package (.mzm)", "أرسل الحزمة (.mzm)"))
    row = await listings.submit(db, t, user.id, data, say=service._)
    await db.commit()
    return listings.version_out(row)


@router.get("/teams/{handle}/packages")
async def team_packages(handle: str, db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    """The team's listings and every version it submitted, with the review outcome."""
    from app.platform.marketplace import listings

    t, _ = await service.membership(db, user, handle)
    return await listings.team_submissions(db, t)


@router.delete("/teams/{handle}/packages/{item_id}/{version}", status_code=204)
async def withdraw_package(handle: str, item_id: str, version: str, db: AsyncSession = Depends(get_db),
                           user: DeveloperUser = Depends(current_developer)):
    from app.platform.marketplace import listings

    t, _ = await service.membership(db, user, handle)
    await listings.withdraw(db, t, item_id, version, say=service._)
    await db.commit()


# ── CLI tokens ────────────────────────────────────────────────────────────────

@router.get("/cli-tokens")
async def list_cli_tokens(db: AsyncSession = Depends(get_db), user: DeveloperUser = Depends(current_developer)):
    return {"items": await service.cli_tokens(db, user)}


@router.post("/cli-tokens", status_code=201)
async def create_cli_token(data: CliTokenIn, db: AsyncSession = Depends(get_db),
                           user: DeveloperUser = Depends(current_developer)):
    return await service.create_cli_token(db, user, data.name)


@router.delete("/cli-tokens/{token_id}", status_code=204)
async def revoke_cli_token(token_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                           user: DeveloperUser = Depends(current_developer)):
    await service.revoke_cli_token(db, user, token_id)

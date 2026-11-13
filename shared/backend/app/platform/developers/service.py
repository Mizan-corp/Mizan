"""The developer portal (ADR-007 D5): accounts, teams, signing keys and CLI tokens.

A developer signs in to the portal (a JWT with scope "developer") or uses the `mizan` CLI with a
token made in the portal (`mzd_…`, only its hash kept); both reach the same endpoints. A team
registers Ed25519 public keys; Mizan certifies each (MZD1, app.framework.package.certify) so an
install can verify the team's packages offline. A revoked key's packages are refused when installed
in the cloud (`key_revoked`).
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.developers.models import (
    DeveloperCliToken,
    DeveloperKey,
    DeveloperTeam,
    DeveloperTeamMember,
    DeveloperUser,
)

SCOPE = "developer"
CLI_PREFIX = "mzd_"
HANDLE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")  # the <developer> part of module ids (manifest.MODULE_ID)
RESERVED = {"mizan", "allmizan", "admin", "platform", "system", "core", "general", "community", "official",
            "owner", "api", "www", "dev", "docs", "support", "test", "example", "acme"}
MAX_KEYS = 10
MAX_TEAMS = 5

# The developer platform speaks English unless the client asks for Arabic (Accept-Language: ar);
# the CLI prints these messages as they come.
LANG: ContextVar[str] = ContextVar("developer_lang", default="en")


def _(en: str, ar: str) -> str:
    return ar if LANG.get() == "ar" else en


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Accounts ─────────────────────────────────────────────────────────────────

async def signup(db: AsyncSession, email: str, full_name: str, password: str) -> DeveloperUser:
    from app.platform.auth.security import hash_password

    email = normalize_email(email)
    if await db.scalar(select(DeveloperUser.id).where(DeveloperUser.email == email)):
        raise HTTPException(409, _("This email is already registered; sign in", "هذا البريد مسجل بالفعل، سجّل الدخول"))
    user = DeveloperUser(email=email, full_name=full_name.strip(), password_hash=hash_password(password),
                         last_login_at=datetime.now(UTC))
    db.add(user)
    await db.commit()
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> DeveloperUser:
    from app.platform.auth.security import verify_password

    user = await db.scalar(select(DeveloperUser).where(DeveloperUser.email == normalize_email(email)))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(401, _("Wrong email or password", "البريد أو كلمة المرور غير صحيحة"))
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    return user


def issue_session(user: DeveloperUser) -> str:
    from app.platform.auth.security import create_access_token

    return create_access_token({"sub": str(user.id), "scope": SCOPE})


async def user_from_token(db: AsyncSession, token: str) -> DeveloperUser:
    """The developer a portal session or CLI token belongs to (401 otherwise)."""
    if token.startswith(CLI_PREFIX):
        row = await db.scalar(select(DeveloperCliToken).where(DeveloperCliToken.token_hash == _hash(token),
                                                              DeveloperCliToken.revoked_at.is_(None)))
        user = await db.get(DeveloperUser, row.user_id) if row else None
        if not user or not user.is_active:
            raise HTTPException(401, _("Invalid or revoked CLI token", "رمز سطر الأوامر غير صالح أو أُلغي"))
        row.last_used_at = datetime.now(UTC)
        await db.commit()
        return user
    from app.platform.auth.security import decode_token
    from app.platform.auth.sessions import ensure_live

    payload = decode_token(token)
    if payload.get("scope") != SCOPE:
        raise HTTPException(401, _("Not a developer session", "هذه الجلسة ليست جلسة مطور"))
    try:
        user = await db.get(DeveloperUser, uuid.UUID(str(payload.get("sub"))))
    except ValueError:
        raise HTTPException(401, "Invalid token") from None
    if not user or not user.is_active:
        raise HTTPException(401, "Not authenticated")
    await ensure_live(db, payload, user.tokens_valid_after)
    user.token_payload = payload
    return user


async def change_password(db: AsyncSession, user: DeveloperUser, current: str, new: str) -> None:
    from app.platform.auth.security import hash_password, verify_password
    from app.platform.auth.sessions import sessions_end_now

    if not verify_password(current, user.password_hash):
        raise HTTPException(400, _("The current password is wrong", "كلمة المرور الحالية غير صحيحة"))
    user.password_hash = hash_password(new)
    user.tokens_valid_after = sessions_end_now()  # every portal session ends; CLI tokens are revoked one by one
    await db.commit()


# ── Teams ─────────────────────────────────────────────────────────────────────

async def teams_of(db: AsyncSession, user: DeveloperUser) -> list[dict]:
    rows = (await db.execute(select(DeveloperTeam, DeveloperTeamMember.role)
                             .join(DeveloperTeamMember, DeveloperTeamMember.team_id == DeveloperTeam.id)
                             .where(DeveloperTeamMember.user_id == user.id).order_by(DeveloperTeam.created_at))).all()
    return [team_out(t, role) for t, role in rows]


def team_out(t: DeveloperTeam, role: str) -> dict:
    return {"id": str(t.id), "handle": t.handle, "name": t.name, "role": role,
            "created_at": t.created_at.isoformat() if t.created_at else None}


async def create_team(db: AsyncSession, user: DeveloperUser, handle: str, name: str) -> dict:
    handle = handle.strip().lower()
    if not HANDLE.match(handle):
        raise HTTPException(422, _("A handle is 2–32 lower-case letters, digits and _, starting with a letter", "المعرّف حروف إنجليزية صغيرة وأرقام و _ ، يبدأ بحرف (2–32)"))
    if handle in RESERVED:
        raise HTTPException(422, _("This handle is reserved", "هذا المعرّف محجوز"))
    if await db.scalar(select(DeveloperTeam.id).where(DeveloperTeam.handle == handle)):
        raise HTTPException(409, _("This handle is taken", "هذا المعرّف مستخدم"))
    count = await db.scalar(select(func.count()).select_from(DeveloperTeamMember)
                            .where(DeveloperTeamMember.user_id == user.id, DeveloperTeamMember.role == "owner"))
    if count >= MAX_TEAMS:
        raise HTTPException(409, _(f"You can create up to {MAX_TEAMS} teams", f"يمكنك إنشاء {MAX_TEAMS} فرق على الأكثر"))
    team = DeveloperTeam(handle=handle, name=name.strip(), created_by=user.id)
    db.add(team)
    await db.flush()
    db.add(DeveloperTeamMember(team_id=team.id, user_id=user.id, role="owner"))
    await db.commit()
    return team_out(team, "owner")


async def membership(db: AsyncSession, user: DeveloperUser, handle: str, owner: bool = False) -> tuple[DeveloperTeam, str]:
    """The team and the user's role in it; 404 when they aren't in it, 403 when `owner` is needed."""
    row = (await db.execute(select(DeveloperTeam, DeveloperTeamMember.role)
                            .join(DeveloperTeamMember, DeveloperTeamMember.team_id == DeveloperTeam.id)
                            .where(DeveloperTeam.handle == handle, DeveloperTeamMember.user_id == user.id))).first()
    if row is None:
        raise HTTPException(404, _("Team not found", "الفريق غير موجود"))
    if owner and row[1] != "owner":
        raise HTTPException(403, _("Only the team's owners can do this", "هذا لمالكي الفريق فقط"))
    return row[0], row[1]


async def members(db: AsyncSession, team: DeveloperTeam) -> list[dict]:
    rows = (await db.execute(select(DeveloperUser, DeveloperTeamMember.role)
                             .join(DeveloperTeamMember, DeveloperTeamMember.user_id == DeveloperUser.id)
                             .where(DeveloperTeamMember.team_id == team.id).order_by(DeveloperTeamMember.created_at))).all()
    return [{"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": role} for u, role in rows]


async def add_member(db: AsyncSession, team: DeveloperTeam, email: str, role: str) -> None:
    """Add a developer who already has a portal account (by their email)."""
    if role not in ("owner", "member"):
        raise HTTPException(422, _("Unknown role", "دور غير معروف"))
    user = await db.scalar(select(DeveloperUser).where(DeveloperUser.email == normalize_email(email)))
    if user is None:
        raise HTTPException(404, _("No developer has this email; ask them to create a portal account first", "لا يوجد مطور بهذا البريد؛ اطلب منه إنشاء حساب في البوابة أولًا"))
    if await db.get(DeveloperTeamMember, (team.id, user.id)):
        raise HTTPException(409, _("Already a member of the team", "عضو في الفريق بالفعل"))
    db.add(DeveloperTeamMember(team_id=team.id, user_id=user.id, role=role))
    await db.commit()


async def remove_member(db: AsyncSession, team: DeveloperTeam, user_id: uuid.UUID) -> None:
    m = await db.get(DeveloperTeamMember, (team.id, user_id))
    if m is None:
        raise HTTPException(404, _("Not a member of the team", "ليس عضوًا في الفريق"))
    if m.role == "owner":
        owners = await db.scalar(select(func.count()).select_from(DeveloperTeamMember)
                                 .where(DeveloperTeamMember.team_id == team.id, DeveloperTeamMember.role == "owner"))
        if owners <= 1:
            raise HTTPException(409, _("The team has one owner; add another owner first", "للفريق مالك واحد؛ أضف مالكًا آخر قبل إزالته"))
    await db.delete(m)
    await db.commit()


# ── Signing keys ──────────────────────────────────────────────────────────────

def key_out(k: DeveloperKey) -> dict:
    return {"id": str(k.id), "key_id": k.key_id, "name": k.name, "public_key": k.public_key, "certificate": k.certificate,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None}


async def keys(db: AsyncSession, team: DeveloperTeam) -> list[dict]:
    rows = (await db.execute(select(DeveloperKey).where(DeveloperKey.team_id == team.id)
                             .order_by(DeveloperKey.created_at.desc()))).scalars()
    return [key_out(k) for k in rows]


async def register_key(db: AsyncSession, team: DeveloperTeam, user: DeveloperUser, name: str, public_key: str) -> dict:
    """Certify a team's Ed25519 public key (base64url, 32 bytes): the certificate packages carry."""
    from app.framework.package import certify
    from app.platform.licensing.keys import LicenceError

    text = public_key.strip()
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, TypeError):
        raw = b""
    if len(raw) != 32:
        raise HTTPException(422, _("Invalid public key: paste it as `mizan keys new` printed it", "المفتاح العام غير صالح: الصقه كما طبعه الأمر mizan keys new"))
    if await db.scalar(select(DeveloperKey.id).where(DeveloperKey.public_key == text, DeveloperKey.revoked_at.is_(None))):
        raise HTTPException(409, _("This key is already registered", "هذا المفتاح مسجل بالفعل"))
    active = await db.scalar(select(func.count()).select_from(DeveloperKey)
                             .where(DeveloperKey.team_id == team.id, DeveloperKey.revoked_at.is_(None)))
    if active >= MAX_KEYS:
        raise HTTPException(409, _(f"A team has up to {MAX_KEYS} active keys; revoke an old one", f"للفريق {MAX_KEYS} مفاتيح فعالة على الأكثر؛ ألغِ مفتاحًا قديمًا"))
    key_id = f"{team.handle}-{secrets.token_hex(4)}"
    try:
        cert = certify(team.handle, key_id, raw)
    except LicenceError:
        raise HTTPException(503, _("Certificates can't be issued right now; try again later", "إصدار الشهادات غير متاح الآن، حاول لاحقًا")) from None
    k = DeveloperKey(team_id=team.id, key_id=key_id, name=(name or "default").strip()[:64], public_key=text,
                     certificate=cert, created_by=user.id)
    db.add(k)
    await db.commit()
    return key_out(k)


async def revoke_key(db: AsyncSession, team: DeveloperTeam, key_id: str) -> None:
    k = await db.scalar(select(DeveloperKey).where(DeveloperKey.team_id == team.id, DeveloperKey.key_id == key_id))
    if k is None:
        raise HTTPException(404, _("Key not found", "المفتاح غير موجود"))
    if k.revoked_at is None:
        k.revoked_at = datetime.now(UTC)
        await db.commit()


async def key_revoked(db: AsyncSession, key_id: str) -> bool:
    """Whether Mizan revoked this certified key (installs in the cloud refuse its packages)."""
    if not key_id:
        return False
    return bool(await db.scalar(select(DeveloperKey.id).where(DeveloperKey.key_id == key_id,
                                                               DeveloperKey.revoked_at.is_not(None))))


# ── CLI tokens ────────────────────────────────────────────────────────────────

def cli_token_out(t: DeveloperCliToken) -> dict:
    return {"id": str(t.id), "name": t.name, "created_at": t.created_at.isoformat() if t.created_at else None,
            "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            "revoked_at": t.revoked_at.isoformat() if t.revoked_at else None}


async def cli_tokens(db: AsyncSession, user: DeveloperUser) -> list[dict]:
    rows = (await db.execute(select(DeveloperCliToken).where(DeveloperCliToken.user_id == user.id,
                                                             DeveloperCliToken.revoked_at.is_(None))
                             .order_by(DeveloperCliToken.created_at.desc()))).scalars()
    return [cli_token_out(t) for t in rows]


async def create_cli_token(db: AsyncSession, user: DeveloperUser, name: str) -> dict:
    """A new CLI token, shown once."""
    token = CLI_PREFIX + secrets.token_urlsafe(32)
    t = DeveloperCliToken(user_id=user.id, name=(name or "CLI").strip()[:64], token_hash=_hash(token))
    db.add(t)
    await db.commit()
    return {**cli_token_out(t), "token": token}


async def revoke_cli_token(db: AsyncSession, user: DeveloperUser, token_id: uuid.UUID) -> None:
    t = await db.scalar(select(DeveloperCliToken).where(DeveloperCliToken.id == token_id,
                                                        DeveloperCliToken.user_id == user.id))
    if t is None:
        raise HTTPException(404, _("Token not found", "الرمز غير موجود"))
    t.revoked_at = t.revoked_at or datetime.now(UTC)
    await db.commit()


async def verify_upload(file, db: AsyncSession, kind: str):
    """A package uploaded to a workspace (a module or a theme): genuine, of the expected kind,
    and not signed with a key revoked in the portal. Arabic messages: the workspace app is Arabic."""
    from app.framework import package as mzm

    data = await file.read(mzm.MAX_BYTES + 1)
    try:
        pkg = mzm.verify(data)
    except mzm.PackageError as e:
        raise HTTPException(422, f"تعذر قبول الحزمة: {e}") from None
    if await key_revoked(db, pkg.key_id):  # ADR-007 D5
        raise HTTPException(422, "تعذر قبول الحزمة: مفتاح توقيع المطور أُلغي")
    if pkg.kind != kind:
        raise HTTPException(422, {
            "theme": "هذه الحزمة مظهر؛ ثبّتها من قسم المظاهر",
            "activity": "هذه الحزمة نشاط تجاري كامل؛ تشغيل الأنشطة من المطورين يأتي مع تغيير نشاط المنشأة",
        }.get(pkg.kind, "هذه الحزمة وحدة؛ ثبّتها من قسم وحدات المطورين"))
    return pkg

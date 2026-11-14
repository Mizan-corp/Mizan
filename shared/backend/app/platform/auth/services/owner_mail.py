"""Owners' email (#71, #72): one-time codes, the verified address, and the emails Mizan sends.

- A **code** is 6 digits, emailed, valid 15 minutes, used once, 5 tries; only its keyed hash is
  stored. Asking again replaces the previous one; at most 3 per hour (and one a minute) per owner
  and purpose. Purposes: `verify_email` (prove the address on the account) and `reset_password`
  (forgot password; only to a verified address).
- **Sent emails** that must go out once (receipts, reminders) are logged by (kind, ref); a failed
  one is forgotten so the next run retries it.
Platform tables: callers use them with no workspace bound.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

logger = logging.getLogger("mizan.owner_mail")

PURPOSES = ("verify_email", "reset_password")
CODE_MINUTES = 15
MAX_ATTEMPTS = 5
PER_HOUR = 3


class OwnerCode(Base):
    __tablename__ = "owner_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("owner_accounts.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OwnerEmailLog(Base):
    __tablename__ = "owner_email_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("owner_accounts.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    ref: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _hash(owner_id, purpose: str, code: str) -> str:
    from app.core.config import settings

    return hmac.new(settings.SECRET_KEY.encode(), f"{owner_id}:{purpose}:{code}".encode(), hashlib.sha256).hexdigest()


def mask(email: str) -> str:
    """a***@gmail.com: enough for the owner to recognise it."""
    user, _, domain = email.partition("@")
    return f"{user[:1]}{'*' * max(2, len(user) - 1)}@{domain}"


def require_email_service() -> None:
    from app.platform.notifications.service import email_enabled

    if not email_enabled():
        raise HTTPException(503, "إرسال البريد غير متاح على هذا الخادم الآن؛ تواصل مع الدعم.")


async def send_code(db: AsyncSession, owner, purpose: str, email: str) -> None:
    """Email a new code (the previous one stops working). Commits."""
    from app.platform.notifications.emails import code_email
    from app.platform.notifications.service import send_email

    assert purpose in PURPOSES
    require_email_service()
    now = datetime.now(UTC)
    recent = (await db.execute(select(OwnerCode.created_at).where(
        OwnerCode.owner_id == owner.id, OwnerCode.purpose == purpose,
        OwnerCode.created_at > now - timedelta(hours=1)).order_by(OwnerCode.created_at.desc()))).scalars().all()
    if recent and recent[0] > now - timedelta(seconds=60):
        raise HTTPException(429, "أُرسل رمز قبل لحظات؛ انتظر دقيقة قبل طلب رمز جديد.")
    if len(recent) >= PER_HOUR:
        raise HTTPException(429, "طلبت رموزًا كثيرة خلال ساعة؛ حاول لاحقًا.")
    await db.execute(update(OwnerCode).where(OwnerCode.owner_id == owner.id, OwnerCode.purpose == purpose,
                                             OwnerCode.used_at.is_(None)).values(used_at=now))
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(OwnerCode(owner_id=owner.id, purpose=purpose, email=email, code_hash=_hash(owner.id, purpose, code),
                     expires_at=now + timedelta(minutes=CODE_MINUTES)))
    await db.commit()
    subject, html, plain = code_email(owner.full_name, code, purpose, CODE_MINUTES)
    result = await send_email(email, subject, html, text=plain)
    if not result.get("ok"):
        raise HTTPException(502, "تعذر إرسال البريد الآن؛ حاول بعد قليل.")


async def check_code(db: AsyncSession, owner, purpose: str, code: str) -> OwnerCode:
    """The owner's current code for `purpose` if `code` matches it (then it's used). Commits."""
    now = datetime.now(UTC)
    row = await db.scalar(select(OwnerCode).where(
        OwnerCode.owner_id == owner.id, OwnerCode.purpose == purpose, OwnerCode.used_at.is_(None),
        OwnerCode.expires_at > now).order_by(OwnerCode.created_at.desc()).limit(1))
    wrong = HTTPException(400, "الرمز غير صحيح أو انتهت صلاحيته؛ اطلب رمزًا جديدًا إن لزم.")
    if row is None or row.attempts >= MAX_ATTEMPTS:
        raise wrong
    if not hmac.compare_digest(row.code_hash, _hash(owner.id, purpose, "".join(c for c in code if c.isdigit()))):
        row.attempts += 1
        if row.attempts >= MAX_ATTEMPTS:
            row.used_at = now  # spent: ask for a new one
        await db.commit()
        raise wrong
    row.used_at = now
    await db.commit()
    return row


async def set_owner_password(db: AsyncSession, owner, password_hash: str) -> int:
    """The owner's new password, also for every workspace login linked to them; every session
    ends (#77). Returns how many workspace logins changed. The caller commits."""
    from app.platform.auth.models.user import User
    from app.platform.auth.services.owners import bypass_rls
    from app.platform.auth.sessions import sessions_end_now

    ended = sessions_end_now()
    owner.password_hash = password_hash
    owner.tokens_valid_after = ended
    await bypass_rls(db)
    changed = await db.execute(update(User).where(User.owner_account_id == owner.id)
                               .values(password_hash=password_hash, tokens_valid_after=ended))
    return changed.rowcount or 0


async def find_for_reset(db: AsyncSession, login_or_email: str):
    """The active owner signing in as `login_or_email`, or whose verified email it is."""
    from app.platform.auth.models.owner import OwnerAccount
    from app.platform.auth.services.owners import normalize_login

    value = login_or_email.strip()
    if "@" in value:
        owner = await db.scalar(select(OwnerAccount).where(func.lower(OwnerAccount.email) == value.lower(),
                                                           OwnerAccount.email_verified_at.is_not(None)).limit(1))
        if owner is None:
            owner = await db.scalar(select(OwnerAccount).where(OwnerAccount.login == normalize_login(value)))
    else:
        owner = await db.scalar(select(OwnerAccount).where(OwnerAccount.login == normalize_login(value)))
    return owner if owner is not None and owner.is_active else None


async def send_once(db: AsyncSession, owner, kind: str, ref: str, subject: str, html: str, plain: str,
                    attachments: list[dict] | None = None) -> bool:
    """Send an email at most once per (kind, ref), to the owner's verified address. Commits."""
    from sqlalchemy.dialects.postgresql import insert

    from app.platform.notifications.service import email_enabled, send_email

    if not (owner and owner.email and owner.email_verified_at and email_enabled()):
        return False
    claimed = await db.execute(insert(OwnerEmailLog).values(owner_id=owner.id, kind=kind, ref=ref, email=owner.email)
                               .on_conflict_do_nothing(index_elements=["kind", "ref"]).returning(OwnerEmailLog.id))
    log_id = claimed.scalar()
    await db.commit()
    if log_id is None:
        return False  # already sent
    result = await send_email(owner.email, subject, html, attachments=attachments, text=plain)
    if not result.get("ok"):  # forget it, so the next run tries again
        await db.execute(delete(OwnerEmailLog).where(OwnerEmailLog.id == log_id))
        await db.commit()
        logger.warning("%s %s to %s failed: %s", kind, ref, owner.email, result.get("error"))
        return False
    return True

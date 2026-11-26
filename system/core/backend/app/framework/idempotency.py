"""Idempotent writes: a retried request returns the first one's result instead of moving money again.

A client that may send the same write twice (a double click, an answer lost on a bad connection, an
offline replay) names the attempt: an `Idempotency-Key` header, or a `client_id` in the body. The
route claims the key in its own transaction before doing the work, and stores its answer in the same
transaction, so either both are saved or neither is:

    replay = await idempotency.claim(db, "safe.deposit", key, payload, user.id)
    if replay is not None:
        return replay
    ... the work ...
    await idempotency.remember(db, "safe.deposit", key, result)
    await db.commit()

A second request with the same key waits for the first to finish (the unique index), then gets its
answer. A failed request leaves no claim, so its retry runs again. The same key with a different
request is refused (422): it is a mistake in the client, not a retry. Keys are kept 7 days
(purge_old, the nightly job `idempotency_cleanup`).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import DateTime, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.platform.tenancy.context import TenantScoped, current_tenant_id

KEY_MAX = 128
KEY_REUSED = "مفتاح منع التكرار مستخدم لعملية مختلفة. أعد المحاولة بمفتاح جديد"
KEY_INVALID = "مفتاح منع التكرار غير صالح (حتى 128 حرفاً من الحروف اللاتينية والأرقام و - _ . :)"
IN_PROGRESS = "العملية نفسها قيد التنفيذ. انتظر قليلاً ثم أعد المحاولة"


class IdempotencyKey(TenantScoped, Base):
    """One claimed key of one kind of write, with the answer it got."""
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "scope", "key", name="uq_idempotency_keys_scope_key"),
                      Index("ix_idempotency_keys_created_at", "created_at"))  # the nightly clean-up

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(KEY_MAX), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def key_of(header: str | None, client_id: uuid.UUID | str | None = None) -> str | None:
    """The attempt's key: the header, else the body's client id; None when the client sent neither."""
    header = header if isinstance(header, str) else None  # a route called directly passes its Header() default
    key = (header or "").strip() or (str(client_id) if client_id else "")
    if not key:
        return None
    if len(key) > KEY_MAX or not all(c.isascii() and (c.isalnum() or c in "-_.:") for c in key):
        raise HTTPException(400, KEY_INVALID)
    return key


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(jsonable_encoder(payload), sort_keys=True).encode()).hexdigest()


async def claim(db: AsyncSession, scope: str, key: str | None, payload: dict, user_id=None) -> dict | None:
    """None: the key is new (or there is none), go ahead. Otherwise the first request's answer."""
    if not key:
        return None
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(400, "لا توجد مساحة عمل مرتبطة")
    digest = _hash(payload)
    claimed = (await db.execute(text("""
        INSERT INTO idempotency_keys (id, tenant_id, scope, key, request_hash, created_by)
        VALUES (gen_random_uuid(), :t, :s, :k, :h, :u)
        ON CONFLICT (tenant_id, scope, key) DO NOTHING
        RETURNING id
    """), {"t": tid, "s": scope, "k": key, "h": digest, "u": user_id})).scalar_one_or_none()
    if claimed is not None:
        return None
    row = (await db.execute(text(
        "SELECT request_hash, response FROM idempotency_keys WHERE tenant_id = :t AND scope = :s AND key = :k"
    ), {"t": tid, "s": scope, "k": key})).one()
    if row.request_hash != digest:
        raise HTTPException(422, KEY_REUSED)
    if row.response is None:
        raise HTTPException(409, IN_PROGRESS)
    return row.response


async def remember(db: AsyncSession, scope: str, key: str | None, response) -> None:
    """Store the answer of a claimed key, in the caller's transaction."""
    if not key:
        return
    await db.execute(text("""
        UPDATE idempotency_keys SET response = CAST(:r AS jsonb)
        WHERE tenant_id = :t AND scope = :s AND key = :k
    """), {"r": json.dumps(jsonable_encoder(response if response is not None else {})), "t": current_tenant_id.get(),
           "s": scope, "k": key})


KEEP_DAYS = 7


async def purge_old(db: AsyncSession, days: int = KEEP_DAYS) -> int:
    """Delete the keys of every workspace older than `days` (the nightly job `idempotency_cleanup`):
    a retry comes within minutes or, from an offline till, within days, never a week later (a key
    is claimed and answered in one transaction, so none is still in progress by then). Runs with no
    workspace bound, so the bypass is set for this transaction only. Returns how many were deleted."""
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    deleted = (await db.execute(text(
        "DELETE FROM idempotency_keys WHERE created_at < now() - make_interval(days => :d)"
    ), {"d": int(days)})).rowcount or 0
    await db.commit()
    return deleted
